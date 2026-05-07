"""Shared decision-normalization helpers for the trading executors.

Both the global trader (`app/trade_executor.py`) and the per-plan executor
(`app/plans/executor.py`) need to coerce degenerate trade decisions to holds
before validation — same contract, separate code paths. Centralizing here
prevents drift between the two: a future change to the rules updates one
place, both call sites get it.

Why coerce instead of validate-and-reject?
  - Claude occasionally returns {action: "buy", quantity: 0} (semantically a
    hold). The parser default also fills 0 if Claude omits the field. These
    are *not* policy violations — they're degenerate inputs that should be
    surfaced as holds with the original intent preserved in the audit trail.
  - Validation messages like "Trade value $0.00 below $1 minimum" are noise
    when the real signal is "Claude didn't actually want to trade this."
"""

import logging

logger = logging.getLogger(__name__)


def coerce_zero_qty_to_hold(decision: dict, log_prefix: str = "") -> bool:
    """Coerce buy/sell with qty <= 0 (or missing) to hold.

    Returns True if the decision was modified. Caller's `decision` dict is
    mutated in place — keeping consistent with the rest of the executor flow.
    """
    if decision.get("action") in ("buy", "sell") and (decision.get("quantity") or 0) <= 0:
        original_qty = decision.get("quantity", 0)
        logger.info(
            "%scoercing %s with qty=%s to hold",
            log_prefix, decision.get("action"), original_qty,
        )
        decision["action"] = "hold"
        decision["quantity"] = 0
        decision["reasoning"] = (
            f"{decision.get('reasoning', '')} "
            f"[Coerced to hold — Claude returned qty={original_qty}]"
        ).strip()
        return True
    return False


def coerce_bad_price_to_hold(decision: dict, price, log_prefix: str = "") -> bool:
    """Coerce buy/sell with bad price (None/0/negative) to hold.

    Use-case: price lookup returned 0 for an exotic symbol or a delisted
    ticker. Without coercion this leaks to validation as `trade_value = 0`
    and produces an "Insufficient $X minimum" block — same noise pattern.
    Caller passes the looked-up `price` so this helper doesn't need to
    know about the broker/quote layer.

    Returns True if modified.
    """
    if decision.get("action") not in ("buy", "sell"):
        return False
    if not price or price <= 0:
        logger.warning(
            "%scoercing %s %s to hold — price=%s",
            log_prefix, decision["action"], decision.get("ticker", ""), price,
        )
        decision["action"] = "hold"
        decision["quantity"] = 0
        decision["reasoning"] = (
            f"{decision.get('reasoning', '')} "
            f"[Coerced to hold — price lookup failed for {decision.get('ticker', '')}]"
        ).strip()
        decision.pop("price", None)
        return True
    return False
