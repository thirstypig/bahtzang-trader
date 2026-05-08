"""Trading constraints enforcement for per-portfolio strategy rules.

Implements cooldown, frequency caps, and no-repeat-action rules to prevent
excessive trading on the same ticker within a portfolio.
"""

from datetime import datetime, timedelta, timezone
from typing import Tuple

from sqlalchemy.orm import Session

from app.models import Trade
from app.plans.models import Portfolio, PortfolioTouchHistory


async def check_trading_constraints(
    db: Session,
    portfolio: Portfolio,
    decision: dict,
    decision_timestamp: datetime,
) -> Tuple[bool, str | None]:
    """Check trading frequency rules before executing trade.

    Enforces:
    1. Cooldown window — min hours between touches on same ticker
    2. Frequency cap — max 5 buys and 5 sells per ticker per week
    3. No-repeat action — can't buy then buy again (or sell then sell)

    Returns: (allowed, reason_if_blocked)
    """

    ticker = decision.get("ticker", "").upper()
    action = decision.get("action", "").upper()

    # Skip validation for holds
    if action == "HOLD":
        return True, None

    # 1. Check per-ticker cooldown
    touch = db.query(PortfolioTouchHistory).filter_by(
        portfolio_id=portfolio.id,
        ticker=ticker,
    ).first()

    if touch:
        hours_elapsed = (decision_timestamp - touch.last_decision_timestamp).total_seconds() / 3600
        if hours_elapsed < portfolio.cooldown_hours:
            reason = f"Cooldown: {ticker} touched {hours_elapsed:.1f}h ago, need {portfolio.cooldown_hours}h"
            return False, reason

    # 2. Check per-ticker frequency (5 buys + 5 sells per week)
    week_start = decision_timestamp - timedelta(days=7)

    buys_this_week = await _count_trades_async(
        db, portfolio.id, ticker, "BUY", week_start
    )

    sells_this_week = await _count_trades_async(
        db, portfolio.id, ticker, "SELL", week_start
    )

    if action == "BUY" and buys_this_week >= 5:
        reason = f"Frequency cap: {ticker} max 5 buys/week, already at 5"
        return False, reason

    if action == "SELL" and sells_this_week >= 5:
        reason = f"Frequency cap: {ticker} max 5 sells/week, already at 5"
        return False, reason

    # 3. Check no same action twice in a row
    if touch and touch.last_action.upper() == action:
        reason = f"No repeats: {ticker} last action was {touch.last_action}, can't repeat"
        return False, reason

    return True, None


async def _count_trades_async(
    db: Session,
    portfolio_id: int,
    ticker: str,
    action: str,
    since: datetime,
) -> int:
    """Count executed trades in a portfolio for a specific action and ticker."""
    return await _run_async(
        lambda: db.query(Trade).filter(
            Trade.portfolio_id == portfolio_id,
            Trade.ticker == ticker,
            Trade.action.ilike(action),
            Trade.timestamp >= since,
            Trade.executed.is_(True),
        ).count()
    )


async def update_touch_history(
    db: Session,
    portfolio: Portfolio,
    trade: Trade,
    decision_timestamp: datetime,
) -> None:
    """Update per-ticker touch history after a successful trade.

    This records when and what action was taken, used by the constraints
    checker for cooldown and no-repeat-action validation.
    """

    ticker = trade.ticker.upper()

    # Find or create the touch record
    touch = db.query(PortfolioTouchHistory).filter_by(
        portfolio_id=portfolio.id,
        ticker=ticker,
    ).first()

    if touch:
        touch.last_decision_timestamp = decision_timestamp
        touch.last_action = trade.action.upper()
        touch.updated_at = datetime.now(timezone.utc)
    else:
        touch = PortfolioTouchHistory(
            portfolio_id=portfolio.id,
            ticker=ticker,
            last_decision_timestamp=decision_timestamp,
            last_action=trade.action.upper(),
        )
        db.add(touch)

    await _run_async(lambda: db.commit())


async def _run_async(sync_func):
    """Helper to run a sync function in the async executor pool."""
    import asyncio
    return await asyncio.to_thread(sync_func)
