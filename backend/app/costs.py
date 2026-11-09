"""Shared cost model — what "after all costs" means (trading charter §1, §4).

Used by the live executor (recording), the weekly report (summing) and the backtester
(simulating), so all three agree on one definition.

Rates change: SEC Section 31 resets each fiscal year, FINRA TAF each January, Claude
prices with model releases. Each constant carries its source and effective date —
re-check them when the date is stale.
"""

from dataclasses import dataclass

# SEC Section 31 fee: $20.60 per $1,000,000 of sale proceeds, effective 2026-04-04
# (SEC Fee Rate Advisory 2026-2). Sells only.
SEC_FEE_PER_DOLLAR = 20.60 / 1_000_000

# FINRA Trading Activity Fee: $0.000195 per share sold, max $9.79 per trade (2026 fee
# schedule, SR-FINRA-2024-019). Sells only.
FINRA_TAF_PER_SHARE = 0.000195
FINRA_TAF_MAX = 9.79

# Estimated tax on net realized short-term gains (charter §4, approved 2026-10-19).
SHORT_TERM_TAX_RATE = 0.24

# Claude Sonnet 4.6 (the model the bot calls), per token. Anthropic price list as of
# 2026-10-06: $3 / 1M input, $15 / 1M output; cache write 1.25× input, read 0.1× input.
CLAUDE_INPUT_PER_TOKEN = 3.00 / 1_000_000
CLAUDE_OUTPUT_PER_TOKEN = 15.00 / 1_000_000
CLAUDE_CACHE_WRITE_PER_TOKEN = CLAUDE_INPUT_PER_TOKEN * 1.25
CLAUDE_CACHE_READ_PER_TOKEN = CLAUDE_INPUT_PER_TOKEN * 0.10

# Backtests have no bid/ask quotes: assume a half-spread of 5 bps (0.05%) per fill.
# An ASSUMPTION, reported as such — realistic for liquid large caps, optimistic for
# cheap or OTC names.
BACKTEST_HALF_SPREAD_BPS = 5


def sell_fees(qty: float, price: float) -> float:
    """Regulatory fees on one sell: SEC Section 31 + FINRA TAF (capped)."""
    proceeds = abs(qty) * price
    taf = min(abs(qty) * FINRA_TAF_PER_SHARE, FINRA_TAF_MAX)
    return proceeds * SEC_FEE_PER_DOLLAR + taf


def half_spread_cost(qty: float, bid: float | None, ask: float | None) -> float | None:
    """Cost of crossing half the bid-ask gap. None when the quote can't be trusted —
    unknown is not zero."""
    if bid is None or ask is None or bid <= 0 or ask <= bid:
        return None
    return abs(qty) * (ask - bid) / 2


def api_cost(usage) -> float:
    """Dollar cost of one Claude response from its ``usage`` (missing fields → 0)."""
    def n(field):
        return getattr(usage, field, None) or 0
    return (
        n("input_tokens") * CLAUDE_INPUT_PER_TOKEN
        + n("output_tokens") * CLAUDE_OUTPUT_PER_TOKEN
        + n("cache_creation_input_tokens") * CLAUDE_CACHE_WRITE_PER_TOKEN
        + n("cache_read_input_tokens") * CLAUDE_CACHE_READ_PER_TOKEN
    )


@dataclass(frozen=True)
class RealizedSell:
    trade_id: int
    ticker: str
    qty: float
    proceeds: float
    cost_basis: float
    gain: float


def realized_sells(trades) -> list[RealizedSell]:
    """Replay executed trades (sorted by timestamp, id) with average-cost accounting;
    one RealizedSell per sell. Same method as compute_virtual_cost_basis."""
    held: dict[str, float] = {}
    cost: dict[str, float] = {}
    out: list[RealizedSell] = []
    for t in trades:
        price = float(t.price) if t.price is not None else 0.0
        qty = float(t.quantity)
        if t.action == "buy":
            held[t.ticker] = held.get(t.ticker, 0.0) + qty
            cost[t.ticker] = cost.get(t.ticker, 0.0) + qty * price
        elif t.action == "sell":
            have = held.get(t.ticker, 0.0)
            avg = cost.get(t.ticker, 0.0) / have if have > 0 else 0.0
            basis = qty * avg
            out.append(RealizedSell(t.id, t.ticker, qty, qty * price, basis, qty * price - basis))
            held[t.ticker] = max(have - qty, 0.0)
            cost[t.ticker] = max(cost.get(t.ticker, 0.0) - basis, 0.0)
    return out


def estimated_tax(gains: list[float]) -> float:
    """24% of the period's NET realized gain, floored at zero (losses offset gains
    within the period; no carry-forward)."""
    return max(sum(gains), 0.0) * SHORT_TERM_TAX_RATE
