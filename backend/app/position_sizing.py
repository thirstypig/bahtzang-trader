"""Kelly Criterion position sizing — quarter-Kelly with confidence modifier.

Maps Claude's confidence score + historical win rate to a position size.
Uses confidence^2 to heavily penalize low-confidence trades.
"""

import logging
import math

from sqlalchemy.orm import Session

from app.models import Trade

logger = logging.getLogger(__name__)


def compute_win_stats(db: Session, min_trades: int = 10) -> tuple[float, float]:
    """
    Compute win rate and avg win/loss ratio from executed trades.
    Returns (win_rate, avg_win_loss_ratio). Returns (0, 0) if insufficient data.
    """
    trades = (
        db.query(Trade)
        .filter(
            Trade.executed.is_(True),
            Trade.action.in_(["buy", "sell"]),
            Trade.price.isnot(None),
        )
        .order_by(Trade.timestamp.desc())
        .limit(60)  # Rolling window of last 60 trades
        .all()
    )

    if len(trades) < min_trades:
        return 0.0, 0.0

    # Use confidence as a proxy for "win" until we have realized P&L tracking
    # Win = Claude confidence > 0.6 AND trade was executed
    wins = [t for t in trades if t.confidence and t.confidence > 0.6]
    losses = [t for t in trades if not t.confidence or t.confidence <= 0.6]

    win_rate = len(wins) / len(trades) if trades else 0

    # Avg win/loss ratio from confidence scores
    avg_win = sum(t.confidence or 0 for t in wins) / len(wins) if wins else 0
    avg_loss = sum(1 - (t.confidence or 0) for t in losses) / len(losses) if losses else 1
    win_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 1

    return win_rate, win_loss_ratio


def kelly_position_size(
    confidence: float,
    portfolio_value: float,
    db: Session,
    kelly_fraction: float = 0.25,
    max_position_pct: float = 0.10,
    earnings_days: int | None = None,
) -> float:
    """
    Quarter-Kelly position sizing with confidence^2 modifier.

    Kelly formula: f* = W - (1-W)/R
    Where W = win probability, R = win/loss ratio

    Returns dollar amount to allocate.
    """
    win_rate, win_loss_ratio = compute_win_stats(db)

    # Not enough data for Kelly — fall back to fixed sizing
    if win_rate <= 0 or win_loss_ratio <= 0:
        return portfolio_value * max_position_pct

    full_kelly = win_rate - (1 - win_rate) / win_loss_ratio

    # Negative Kelly = no edge, don't bet
    if full_kelly <= 0:
        logger.info("Kelly fraction is negative (%.3f) — no edge detected", full_kelly)
        return 0.0

    # Apply fractional Kelly
    fraction = full_kelly * kelly_fraction

    # Scale by Claude's confidence squared (penalizes low confidence heavily)
    # At 0.5 confidence → multiplier = 0.25 (not 0.5)
    # At 0.8 confidence → multiplier = 0.64
    # At 1.0 confidence → multiplier = 1.0
    confidence_modifier = min(confidence, 1.0) ** 2
    fraction *= confidence_modifier

    # Earnings proximity reduction: halve position size near earnings
    if earnings_days is not None:
        if earnings_days <= 1:
            fraction *= 0.50
            logger.info("Earnings in %d days — reducing position to 50%%", earnings_days)
        elif earnings_days == 2:
            fraction *= 0.70
            logger.info("Earnings in %d days — reducing position to 70%%", earnings_days)

    # Hard cap
    fraction = min(fraction, max_position_pct)

    position_size = portfolio_value * fraction

    logger.info(
        "Kelly sizing: full=%.3f, fraction=%.3f, confidence_mod=%.3f → $%.0f (%.1f%% of portfolio)",
        full_kelly, kelly_fraction, confidence_modifier,
        position_size, fraction * 100,
    )

    return round(position_size, 2)
