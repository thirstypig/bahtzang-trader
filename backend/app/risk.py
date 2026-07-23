"""Risk engine — position sizing and stop placement.

The core principle: risk is defined BEFORE entry. You choose what you are willing to
lose; the position size falls out of the stop distance. Volatile names therefore get
smaller positions automatically — the opposite of what a momentum screener pushes toward.

Lives at the app level (shared infra), not inside plans/, so the backtester can reuse it
without an isolation violation.
"""

import math

DEFAULT_ATR_MULTIPLE = 2.0
DEFAULT_RISK_PCT = 0.01


class RiskError(ValueError):
    """A trade cannot be sized or stopped safely and must be skipped.

    Raised rather than returning a fudged number — a guessed stop is how you get a
    -24% exit. Missing data must never become a tradeable value.
    """


def compute_stop_price(
    entry_price: float, atr: float | None, atr_multiple: float = DEFAULT_ATR_MULTIPLE
) -> float:
    """Stop placed atr_multiple × ATR below entry (for a long).

    Raises RiskError if ATR is missing or non-positive — no ATR, no computable stop.
    """
    if atr is None or atr <= 0:
        raise RiskError(f"cannot place a stop without a positive ATR (got {atr!r})")
    return entry_price - atr_multiple * atr


def compute_position_size(
    equity: float, risk_pct: float, entry_price: float, stop_price: float
) -> int:
    """Whole-share quantity such that a stop-out loses ~ risk_pct × equity.

    Returns 0 when the risk budget can't afford a single share (caller skips the trade).
    Raises RiskError if the stop is not below entry.
    """
    stop_distance = entry_price - stop_price
    if stop_distance <= 0:
        raise RiskError(
            f"stop {stop_price} must be below entry {entry_price} for a long"
        )
    risk_budget = equity * risk_pct
    return math.floor(risk_budget / stop_distance)
