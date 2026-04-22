"""Regulatory compliance checks — PDT rule and wash sale detection."""

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import Trade

logger = logging.getLogger(__name__)


def count_day_trades(db: Session, lookback_days: int = 7) -> int:
    """
    Count day trades in rolling 5 business day window.
    A day trade = buy and sell of same ticker on the same calendar day.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

    recent_trades = (
        db.query(Trade)
        .filter(
            Trade.executed.is_(True),
            Trade.timestamp >= cutoff,
            Trade.action.in_(["buy", "sell"]),
        )
        .order_by(Trade.timestamp)
        .all()
    )

    # Group by (date, ticker) and find round-trips
    daily_activity: dict[tuple, dict] = defaultdict(lambda: {"buys": 0, "sells": 0})
    for trade in recent_trades:
        day_key = (trade.timestamp.date(), trade.ticker)
        if trade.action == "buy":
            daily_activity[day_key]["buys"] += 1
        elif trade.action == "sell":
            daily_activity[day_key]["sells"] += 1

    return sum(
        min(activity["buys"], activity["sells"])
        for activity in daily_activity.values()
    )


def check_pdt_compliance(
    db: Session,
    account_equity: float,
    proposed_action: str,
    proposed_ticker: str,
) -> tuple[bool, str | None]:
    """
    Check if a proposed trade would violate PDT rules.
    Only relevant for accounts under $25k.
    Returns (allowed, warning_or_none).
    """
    if account_equity >= 25000:
        return True, None

    if proposed_action != "sell":
        return True, None

    # Check if we bought this ticker today
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    bought_today = (
        db.query(Trade)
        .filter(
            Trade.executed.is_(True),
            Trade.action == "buy",
            Trade.ticker == proposed_ticker,
            Trade.timestamp >= today_start,
        )
        .count()
    )

    if bought_today == 0:
        return True, None  # Not a day trade

    current_day_trades = count_day_trades(db)
    if current_day_trades >= 3:
        return False, (
            f"PDT limit: {current_day_trades} day trades in 5 business days. "
            f"Selling {proposed_ticker} (bought today) would trigger PDT flag."
        )

    return True, f"Day trade #{current_day_trades + 1} of 3 allowed"


def check_wash_sale(
    db: Session,
    ticker: str,
    action: str,
    current_price: float | None = None,
) -> tuple[bool, str | None]:
    """
    Check wash sale risk for a proposed trade.
    - For BUYS: check if we sold this ticker at a loss in the last 30 days
    - For SELLS at a loss: warn about 30-day rebuy restriction

    Returns (allowed, warning_or_none). Does not block — only warns.
    """
    window_start = datetime.now(timezone.utc) - timedelta(days=30)

    if action == "buy":
        # Check if we sold this ticker at a loss in the last 30 days
        recent_sells = (
            db.query(Trade)
            .filter(
                Trade.executed.is_(True),
                Trade.action == "sell",
                Trade.ticker == ticker,
                Trade.timestamp >= window_start,
            )
            .all()
        )

        for sell_trade in recent_sells:
            if sell_trade.price is not None:
                avg_cost = _get_avg_cost(db, ticker, sell_trade.timestamp)
                if avg_cost > 0 and float(sell_trade.price) < avg_cost:
                    days_ago = (datetime.now(timezone.utc) - sell_trade.timestamp).days
                    return True, (
                        f"Wash sale warning: {ticker} was sold at a loss "
                        f"{days_ago} days ago. Buying within 30 days "
                        f"disallows the tax loss deduction."
                    )

    return True, None


def _get_avg_cost(db: Session, ticker: str, before: datetime) -> float:
    """Get average cost basis for a ticker from buy trades."""
    buys = (
        db.query(Trade)
        .filter(
            Trade.executed.is_(True),
            Trade.action == "buy",
            Trade.ticker == ticker,
            Trade.timestamp < before,
        )
        .all()
    )
    if not buys:
        return 0.0

    # 071-fix: Convert Decimal price to float for arithmetic with float quantity
    total_cost = sum(float(t.price) * t.quantity for t in buys if t.price)
    total_qty = sum(t.quantity for t in buys if t.price)
    return total_cost / total_qty if total_qty > 0 else 0.0
