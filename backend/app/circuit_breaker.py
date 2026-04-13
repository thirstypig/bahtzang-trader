"""Three-tier circuit breaker — triggers on portfolio drawdown, not market volatility.

YELLOW: daily loss > 3% → halve position sizes (auto-reset next day)
ORANGE: weekly loss > 7% or 3+ consecutive losses → halt buys (auto-reset next day)
RED:    daily loss > 5% or 5+ consecutive losses → full halt via kill switch (manual reset)
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import PortfolioSnapshot, Trade

logger = logging.getLogger(__name__)

YELLOW = "yellow"
ORANGE = "orange"
RED = "red"


def check_circuit_breakers(
    db: Session,
    portfolio_value: float,
    config: dict,
) -> tuple[str | None, str | None]:
    """
    Check circuit breakers based on portfolio P&L.
    Returns (level, reason) or (None, None) if all clear.

    Triggers on YOUR drawdown, not market moves.
    """
    daily_pct = config.get("circuit_breaker_daily_pct", 0.05)
    weekly_pct = config.get("circuit_breaker_weekly_pct", 0.10)

    # Get recent snapshots for P&L calculation
    today = datetime.now(timezone.utc).date()
    week_ago = today - timedelta(days=7)

    snapshots = (
        db.query(PortfolioSnapshot)
        .filter(PortfolioSnapshot.date >= week_ago)
        .order_by(PortfolioSnapshot.date)
        .all()
    )

    if len(snapshots) < 2:
        # Not enough data to compute drawdown — pass
        return None, None

    latest_equity = portfolio_value
    yesterday_equity = snapshots[-1].total_equity if snapshots else latest_equity
    week_start_equity = snapshots[0].total_equity

    # Daily P&L
    daily_pnl_pct = (latest_equity - yesterday_equity) / yesterday_equity if yesterday_equity > 0 else 0

    # RED: daily loss > 5%
    if daily_pnl_pct <= -daily_pct:
        return RED, f"Daily loss {daily_pnl_pct:.1%} exceeds {daily_pct:.0%} — full halt"

    # Weekly P&L
    weekly_pnl_pct = (latest_equity - week_start_equity) / week_start_equity if week_start_equity > 0 else 0

    # RED: weekly loss > 10%
    if weekly_pnl_pct <= -weekly_pct:
        return RED, f"Weekly loss {weekly_pnl_pct:.1%} exceeds {weekly_pct:.0%} — full halt"

    # Check consecutive losses
    consecutive = _count_consecutive_losses(db)

    if consecutive >= 5:
        return RED, f"{consecutive} consecutive losing trades — full halt"

    # ORANGE: weekly loss > 7% or 3+ consecutive losses
    if weekly_pnl_pct <= -(weekly_pct * 0.7):
        return ORANGE, f"Weekly loss {weekly_pnl_pct:.1%} exceeds {weekly_pct * 0.7:.0%} — buys halted"

    if consecutive >= 3:
        return ORANGE, f"{consecutive} consecutive losing trades — buys halted"

    # YELLOW: daily loss > 3%
    if daily_pnl_pct <= -(daily_pct * 0.6):
        return YELLOW, f"Daily loss {daily_pnl_pct:.1%} — reducing position sizes"

    return None, None


def _count_consecutive_losses(db: Session) -> int:
    """Count consecutive losing trades (most recent first)."""
    recent_trades = (
        db.query(Trade)
        .filter(
            Trade.executed.is_(True),
            Trade.action.in_(["buy", "sell"]),
        )
        .order_by(Trade.timestamp.desc())
        .limit(10)
        .all()
    )

    consecutive = 0
    for trade in recent_trades:
        # A "loss" is a sell below average cost
        # For simplicity, check if guardrails blocked it or if it was a losing sell
        if trade.action == "sell" and trade.price is not None:
            # We'd need cost basis tracking for accurate P&L
            # For now, use a proxy: was this a forced sell (confidence < 0.5)?
            if trade.confidence is not None and trade.confidence < 0.5:
                consecutive += 1
            else:
                break
        else:
            break

    return consecutive
