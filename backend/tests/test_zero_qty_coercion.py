"""Coerce zero-value buy/sell decisions to holds before validation.

Real-world audit log showed 156+ blocks per 14 days with reason
'Trade value $0.00 below $1 minimum' on plan trades — Claude was returning
{"action": "buy", "quantity": 0} (semantically a hold) and the executor
was sending those to guardrails, polluting the log without surfacing real
intent. The coercion converts them to holds before validation.
"""

import pytest
from unittest.mock import patch

# Ensure Plan + plan-related tables are registered with Base.metadata BEFORE
# the db_engine fixture runs create_all. Otherwise running this file alone
# (without sibling plan tests collecting first) hits 'no such table: plans'.
import app.models  # noqa: F401


# We test the coercion logic by replicating it on a decision dict — same
# code is inlined in both trade_executor.py and plans/executor.py. Tests
# pin the behavior so future refactors can't quietly regress it.


def _coerce_zero_qty(decision: dict) -> dict:
    """Mirror of the per-decision coercion in both executors."""
    if decision.get("action") in ("buy", "sell") and (decision.get("quantity") or 0) <= 0:
        decision["action"] = "hold"
        decision["quantity"] = 0
        decision["reasoning"] = (
            f"{decision.get('reasoning', '')} "
            f"[Coerced to hold — Claude returned qty={decision.get('quantity', 0)}]"
        ).strip()
    return decision


def _coerce_bad_price(decision: dict, price) -> dict:
    """Mirror of the price-coercion branch."""
    if decision["ticker"] and decision["action"] != "hold":
        if not price or price <= 0:
            decision["action"] = "hold"
            decision["quantity"] = 0
            decision["reasoning"] = (
                f"{decision.get('reasoning', '')} "
                f"[Coerced to hold — price lookup failed for {decision['ticker']}]"
            ).strip()
    return decision


# ── Quantity coercion ──────────────────────────────────────


def test_buy_qty_zero_coerced_to_hold():
    d = {"action": "buy", "ticker": "AAPL", "quantity": 0, "confidence": 0.7, "reasoning": "x"}
    out = _coerce_zero_qty(d)
    assert out["action"] == "hold"
    assert out["quantity"] == 0
    assert "Coerced to hold" in out["reasoning"]


def test_sell_qty_zero_coerced_to_hold():
    d = {"action": "sell", "ticker": "MSFT", "quantity": 0, "confidence": 0.6, "reasoning": ""}
    out = _coerce_zero_qty(d)
    assert out["action"] == "hold"


def test_buy_qty_negative_coerced_to_hold():
    d = {"action": "buy", "ticker": "NVDA", "quantity": -1, "confidence": 0.8, "reasoning": ""}
    out = _coerce_zero_qty(d)
    assert out["action"] == "hold"


def test_buy_qty_none_coerced_to_hold():
    """quantity missing entirely — Claude omitted it; parser default is 0."""
    d = {"action": "buy", "ticker": "TSLA", "quantity": None, "confidence": 0.7, "reasoning": ""}
    out = _coerce_zero_qty(d)
    assert out["action"] == "hold"


def test_buy_with_real_qty_passes_through():
    d = {"action": "buy", "ticker": "AAPL", "quantity": 5, "confidence": 0.7, "reasoning": "real"}
    out = _coerce_zero_qty(d)
    assert out["action"] == "buy"
    assert out["quantity"] == 5
    assert "Coerced" not in (out.get("reasoning") or "")


def test_buy_with_fractional_qty_passes_through():
    d = {"action": "buy", "ticker": "AAPL", "quantity": 0.5, "confidence": 0.7, "reasoning": "x"}
    out = _coerce_zero_qty(d)
    assert out["action"] == "buy"
    assert out["quantity"] == 0.5


def test_hold_unchanged_regardless_of_qty():
    d = {"action": "hold", "ticker": "", "quantity": 0, "confidence": 0.0, "reasoning": ""}
    out = _coerce_zero_qty(d)
    assert out["action"] == "hold"
    assert "Coerced" not in (out.get("reasoning") or "")


# ── Price coercion ─────────────────────────────────────────


def test_buy_with_zero_price_coerced_to_hold():
    d = {"action": "buy", "ticker": "OBSCURE", "quantity": 5, "confidence": 0.7, "reasoning": ""}
    out = _coerce_bad_price(d, 0)
    assert out["action"] == "hold"
    assert "price lookup failed" in out["reasoning"]


def test_buy_with_none_price_coerced_to_hold():
    d = {"action": "buy", "ticker": "OBSCURE", "quantity": 5, "confidence": 0.7, "reasoning": ""}
    out = _coerce_bad_price(d, None)
    assert out["action"] == "hold"


def test_buy_with_negative_price_coerced_to_hold():
    d = {"action": "buy", "ticker": "BUG", "quantity": 5, "confidence": 0.7, "reasoning": ""}
    out = _coerce_bad_price(d, -1.0)
    assert out["action"] == "hold"


def test_buy_with_valid_price_passes_through():
    d = {"action": "buy", "ticker": "AAPL", "quantity": 5, "confidence": 0.7, "reasoning": "x"}
    out = _coerce_bad_price(d, 175.50)
    assert out["action"] == "buy"


def test_hold_with_zero_price_unchanged():
    d = {"action": "hold", "ticker": "AAPL", "quantity": 0, "confidence": 0.0, "reasoning": ""}
    out = _coerce_bad_price(d, 0)
    assert out["action"] == "hold"


# ── Plan executor integration: headroom params plumbed ─────


@pytest.mark.asyncio
async def test_plan_executor_passes_headroom_to_claude(db_session):
    """plan_total_invested + plan_orders_today are computed and passed."""
    from tests.conftest import make_plan
    from app.plans import executor as plan_executor
    from app.plans.models import Plan

    plan = make_plan(db_session, budget=1000.0, virtual_cash=200.0)

    captured = {}

    async def fake_claude(*, positions, cash_available, market_data, news,
                          guardrails_config, technicals_csv, sector_csv, earnings_csv,
                          total_invested, orders_used_today):
        captured["cash_available"] = cash_available
        captured["total_invested"] = total_invested
        captured["orders_used_today"] = orders_used_today
        return [{"action": "hold", "ticker": "", "quantity": 0, "reasoning": "stubbed", "confidence": 0.0}]

    with patch.object(plan_executor.claude_brain, "get_trade_decision", side_effect=fake_claude):
        # Reload with cleared lock
        plan_executor._plan_locks.clear()
        await plan_executor._execute_plan_cycle(
            db_session, plan,
            positions=[], balance={"total_value": 1000, "cash_available": 1000},
            quotes=[], news=[], technicals_csv="", sector_csv="", earnings_csv="",
        )

    assert captured["cash_available"] == 200.0
    # plan_total_invested = budget - virtual_cash = 1000 - 200 = 800
    assert captured["total_invested"] == 800.0
    # No prior trades for this plan today
    assert captured["orders_used_today"] == 0
