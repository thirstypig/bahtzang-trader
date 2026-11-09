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

    Enforces, for BUYS only:
    1. Cooldown window — min hours since the last touch (buy or sell) on the ticker
    2. Frequency cap — max 5 buys per ticker per week

    Sells always pass (trading charter §3: "Selling is always allowed. The cooldown
    applies to buys only"). Blocking a sell is how a loser gets held past the
    decision to cut it. A sell still updates touch history, so a re-buy right after
    it waits out the cooldown — that's the churn the cooldown exists to stop.

    Returns: (allowed, reason_if_blocked)
    """

    ticker = decision.get("ticker", "").upper()
    action = decision.get("action", "").upper()

    # Holds and sells are never blocked here.
    if action in ("HOLD", "SELL"):
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

    # 2. Check per-ticker buy frequency (5 per week)
    week_start = decision_timestamp - timedelta(days=7)
    buys_this_week = await _count_trades_async(
        db, portfolio.id, ticker, "BUY", week_start
    )
    if action == "BUY" and buys_this_week >= 5:
        reason = f"Frequency cap: {ticker} max 5 buys/week, already at 5"
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
