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


MAX_POSITION_PCT = 0.20  # charter §3: biggest single position ≤ 20% of the portfolio
CASH_BUFFER = 0.95  # leave 5% of cash for slippage between quote and fill

# Charter 2026-11-09: two strategies. (risk per trade, biggest single position).
# Anything else gets the charter caps (1%, 20%).
PROFILE_LIMITS = {
    "conservative": (0.005, 0.10),
    "aggressive": (0.01, 0.20),
}


def limits_for_profile(profile: str | None) -> tuple[float, float]:
    """(risk_pct, max_position_pct) for a portfolio's risk profile."""
    return PROFILE_LIMITS.get(profile or "", (DEFAULT_RISK_PCT, MAX_POSITION_PCT))


def round_stop_price(price: float) -> float:
    """Round a stop DOWN to a tick Alpaca accepts.

    Alpaca rejects sub-penny prices: $1 and up trade in $0.01 ticks, below $1 in
    $0.0001. Rounding down keeps the stop at or below the computed level (never
    tighter than the risk math intended). The epsilon stops float noise turning an
    exact 11.57 into 11.56.
    """
    scale = 100 if price >= 1 else 10_000
    return math.floor(price * scale + 1e-6) / scale


def _earnings_factor(earnings_days: int | None) -> float:
    """Shrink entries right before earnings — a gap can jump straight past the stop."""
    if earnings_days is None or earnings_days < 0:
        return 1.0
    if earnings_days <= 1:
        return 0.5
    if earnings_days == 2:
        return 0.7
    return 1.0


def size_entry(
    *,
    portfolio_value: float,
    cash: float,
    entry_price: float,
    atr: float | None,
    earnings_days: int | None = None,
    held_value: float = 0.0,
    risk_pct: float = DEFAULT_RISK_PCT,
    max_position_pct: float = MAX_POSITION_PCT,
) -> tuple[int, float]:
    """Whole-share quantity and broker stop price for a new long entry.

    qty = min(risk-sized, affordable with CASH_BUFFER, MAX_POSITION_PCT of portfolio),
    then the earnings factor, floored. ``held_value`` is what the portfolio already
    holds in this ticker — the 20% cap is per position, not per order. A risk-sized qty alone can be leveraged (tight
    stop → huge size), so the caps are part of the contract, not an afterthought.

    Returns (0, stop) when not even one share fits — the caller skips the trade.
    Raises RiskError when no safe stop exists (no ATR, stop at or below zero).
    """
    stop = round_stop_price(compute_stop_price(entry_price, atr))
    if stop <= 0:
        raise RiskError(f"stop {stop} is not above zero for entry {entry_price}")
    risk_qty = compute_position_size(portfolio_value, risk_pct, entry_price, stop)
    cash_qty = math.floor(max(cash, 0) * CASH_BUFFER / entry_price)
    cap_qty = math.floor(
        max(portfolio_value * max_position_pct - held_value, 0) / entry_price
    )
    qty = min(risk_qty, cash_qty, cap_qty)
    qty = math.floor(qty * _earnings_factor(earnings_days))
    return max(qty, 0), stop
