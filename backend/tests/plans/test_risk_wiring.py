"""Risk engine wired into the live cycle (PRD-002 Phase 1, charter §3 row 1).

Every stock buy — every decision mode, every run path (scheduler, /run, Run Now all
call run_plan_cycle) — is sized by app.risk.size_entry and sent with a broker-held
stop; fired stops reach the ledger before decisions; sells release their own stop.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, call, patch

from app.models import Trade
from tests.test_executor_decision_modes import _make_rules_portfolio

# $10k plan, AAPL $50, ATR stub 2.0 → stop 46.0, risk qty 100/4 = 25 (cash/20% caps looser)
_QUOTES = [{"ticker": "AAPL", "price": 50.0, "change_pct": 0.0, "volume": 1_000_000}]
_BALANCE = {"cash_available": 50_000.0, "total_value": 100_000.0}


def _decision(action, qty):
    return [{"action": action, "ticker": "AAPL", "quantity": qty, "reasoning": "signal",
             "confidence": 0.75}]


def _broker(get_order=None):
    b = MagicMock()
    b.place_order = AsyncMock(return_value={"order_id": "ord-1", "status": "accepted",
                                            "filled_qty": 0, "stop_order_id": "leg-new"})
    b.get_order = AsyncMock(return_value=get_order or {"status": "held", "filled_qty": 0.0,
                                                        "filled_avg_price": None})
    b.cancel_order = AsyncMock(return_value="canceled")
    b.place_stop_order = AsyncMock(return_value={"order_id": "stop-rem", "status": "new"})
    return b


async def _run(db, plan):
    from app.plans.executor import run_plan_cycle
    return await run_plan_cycle(db, plan, [], _BALANCE, _QUOTES, [], "", "", "")


def _seed_open_buy(db, plan, qty=10.0):
    t = Trade(portfolio_id=plan.id, ticker="AAPL", action="buy", quantity=qty, price=50.0,
              executed=True, guardrail_passed=True, stop_price=46.0,
              stop_order_id="leg-1", stop_state="open")
    db.add(t)
    plan.virtual_cash = float(plan.virtual_cash) - qty * 50.0
    db.commit()
    return t


@pytest.fixture(autouse=True)
def _quiet_slack():
    with patch("app.plans.stops.notifier.notify_risk_event", new_callable=AsyncMock):
        yield


@pytest.mark.integration
class TestBuysAreRiskSized:
    async def test_claude_qty_replaced_by_risk_size(self, db_session):
        plan = _make_rules_portfolio(db_session, "claude_decides")
        b = _broker()
        with patch("app.plans.executor.claude_brain.get_trade_decision",
                   new_callable=AsyncMock, return_value=_decision("buy", 50)), \
             patch("app.plans.executor.broker", b):
            results = await _run(db_session, plan)

        b.place_order.assert_awaited_once()
        kw = b.place_order.await_args.kwargs
        assert (kw["quantity"], kw["stop_price"]) == (25, 46.0)
        row = db_session.get(Trade, results[0]["trade_id"])
        assert (row.quantity, float(row.stop_price), row.stop_order_id, row.stop_state) == \
            (25, 46.0, "leg-new", "open")
        assert "Risk engine" in row.claude_reasoning

    async def test_rules_mode_buy_also_gets_stop(self, db_session):
        plan = _make_rules_portfolio(db_session, "rules_decide")
        b = _broker()
        with patch("app.plans.executor._get_strategy_decisions",
                   new_callable=AsyncMock, return_value=_decision("buy", 3)), \
             patch("app.plans.executor.broker", b):
            await _run(db_session, plan)

        assert b.place_order.await_args.kwargs["stop_price"] == 46.0
        assert b.place_order.await_args.kwargs["quantity"] == 25

    async def test_no_atr_buy_becomes_hold(self, db_session):
        plan = _make_rules_portfolio(db_session, "claude_decides")
        b = _broker()
        with patch("app.plans.executor.claude_brain.get_trade_decision",
                   new_callable=AsyncMock, return_value=_decision("buy", 5)), \
             patch("app.plans.executor.broker", b), \
             patch("app.plans.executor._fetch_atr", new_callable=AsyncMock, return_value=None):
            results = await _run(db_session, plan)

        b.place_order.assert_not_awaited()
        assert results[0]["action"] == "hold"
        assert "Risk engine" in results[0]["reasoning"]


@pytest.mark.integration
class TestStopLifecycleInCycle:
    async def test_fired_stop_recorded_before_decisions(self, db_session):
        plan = _make_rules_portfolio(db_session, "claude_decides")
        _seed_open_buy(db_session, plan)  # cash 9,500
        b = _broker(get_order={"status": "filled", "filled_qty": 10.0, "filled_avg_price": 46.0})
        with patch("app.plans.executor.claude_brain.get_trade_decision",
                   new_callable=AsyncMock, return_value=_decision("hold", 0)) as claude, \
             patch("app.plans.executor.broker", b):
            await _run(db_session, plan)

        held = [p["instrument"]["symbol"] for p in claude.await_args.kwargs["positions"]]
        assert "AAPL" not in held
        assert claude.await_args.kwargs["cash_available"] == 9_960.0
        db_session.refresh(plan)
        assert float(plan.virtual_cash) == 9_960.0

    async def test_sell_releases_stop_then_sells(self, db_session):
        plan = _make_rules_portfolio(db_session, "claude_decides")
        _seed_open_buy(db_session, plan)
        b = _broker()
        order = MagicMock()
        order.attach_mock(b.cancel_order, "cancel")
        order.attach_mock(b.place_order, "place")
        with patch("app.plans.executor.claude_brain.get_trade_decision",
                   new_callable=AsyncMock, return_value=_decision("sell", 10)), \
             patch("app.plans.executor.broker", b):
            results = await _run(db_session, plan)

        names = [c[0] for c in order.mock_calls]
        assert names.index("cancel") < names.index("place")
        assert results[0]["executed"] is True
        b.place_stop_order.assert_not_awaited()  # full exit: nothing left to protect

    async def test_sell_skipped_when_stop_already_fired(self, db_session):
        plan = _make_rules_portfolio(db_session, "claude_decides")
        _seed_open_buy(db_session, plan)
        b = _broker()
        # Held at reconcile time, fires before the sell's cancel lands.
        b.cancel_order = AsyncMock(return_value="filled")
        b.get_order = AsyncMock(side_effect=[
            {"status": "held", "filled_qty": 0.0, "filled_avg_price": None},
            {"status": "filled", "filled_qty": 10.0, "filled_avg_price": 46.0},
        ])
        with patch("app.plans.executor.claude_brain.get_trade_decision",
                   new_callable=AsyncMock, return_value=_decision("sell", 10)), \
             patch("app.plans.executor.broker", b):
            results = await _run(db_session, plan)

        b.place_order.assert_not_awaited()
        assert results[0]["executed"] is False
        assert "stop already fired" in results[0]["guardrail_block_reason"]

    async def test_partial_sell_reprotects_remainder(self, db_session):
        plan = _make_rules_portfolio(db_session, "claude_decides")
        _seed_open_buy(db_session, plan)
        b = _broker()
        with patch("app.plans.executor.claude_brain.get_trade_decision",
                   new_callable=AsyncMock, return_value=_decision("sell", 4)), \
             patch("app.plans.executor.broker", b):
            results = await _run(db_session, plan)

        b.place_stop_order.assert_awaited_once_with("AAPL", 6, 46.0)
        row = db_session.get(Trade, results[0]["trade_id"])
        assert (row.stop_order_id, row.stop_state) == ("stop-rem", "open")


@pytest.mark.integration
class TestReviewFixesInCycle:
    async def test_sell_order_failure_restores_stop(self, db_session):
        """C1: stop cancelled, sell rejected → the whole position gets a stop again."""
        plan = _make_rules_portfolio(db_session, "claude_decides")
        _seed_open_buy(db_session, plan)
        b = _broker()
        b.place_order = AsyncMock(side_effect=RuntimeError("symbol halted"))
        with patch("app.plans.executor.claude_brain.get_trade_decision",
                   new_callable=AsyncMock, return_value=_decision("sell", 4)), \
             patch("app.plans.executor.broker", b):
            results = await _run(db_session, plan)

        assert results[0]["executed"] is False
        b.place_stop_order.assert_awaited_once_with("AAPL", 10, 46.0)

    async def test_add_respects_20pct_with_existing_holding(self, db_session):
        """I1: hold 36 AAPL @ $50 = $1,800 → only 4 more shares fit under 20%."""
        plan = _make_rules_portfolio(db_session, "claude_decides")
        _seed_open_buy(db_session, plan, qty=36.0)
        b = _broker()
        with patch("app.plans.executor.claude_brain.get_trade_decision",
                   new_callable=AsyncMock, return_value=_decision("buy", 50)), \
             patch("app.plans.executor.broker", b):
            await _run(db_session, plan)

        assert b.place_order.await_args.kwargs["quantity"] == 4

    async def test_missing_stop_leg_alerts(self, db_session):
        """I2: stop requested but Alpaca returned no leg id → Slack, never silent."""
        plan = _make_rules_portfolio(db_session, "claude_decides")
        b = _broker()
        b.place_order = AsyncMock(return_value={"order_id": "ord-1", "status": "accepted",
                                                "filled_qty": 0, "stop_order_id": None})
        with patch("app.plans.executor.claude_brain.get_trade_decision",
                   new_callable=AsyncMock, return_value=_decision("buy", 5)), \
             patch("app.plans.executor.broker", b), \
             patch("app.plans.executor.notifier.notify_risk_event", new_callable=AsyncMock) as alert:
            await _run(db_session, plan)

        assert "stop" in alert.await_args.args[0].lower()

    async def test_second_sell_after_release_fill_is_blocked(self, db_session):
        """I3: release records a fill → a later same-ticker sell sees 0 shares."""
        plan = _make_rules_portfolio(db_session, "claude_decides")
        _seed_open_buy(db_session, plan)
        b = _broker()
        b.cancel_order = AsyncMock(return_value="filled")
        b.get_order = AsyncMock(side_effect=[
            {"status": "held", "filled_qty": 0.0, "filled_avg_price": None},
            {"status": "filled", "filled_qty": 10.0, "filled_avg_price": 46.0},
        ])
        two = _decision("sell", 10) + _decision("sell", 10)
        with patch("app.plans.executor.claude_brain.get_trade_decision",
                   new_callable=AsyncMock, return_value=two), \
             patch("app.plans.executor.broker", b):
            await _run(db_session, plan)

        b.place_order.assert_not_awaited()
