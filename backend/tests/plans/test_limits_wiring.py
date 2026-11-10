"""Charter §3 limits wired into the live cycle — every run path goes through
run_plan_cycle → _execute_plan_cycle, so these cover scheduler, /run and Run Now."""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.models import Trade
from app.plans.limits import today_et
from app.plans.models import PlanSnapshot
from tests.test_executor_decision_modes import _make_rules_portfolio

_QUOTES = [
    {"ticker": "AAPL", "price": 50.0, "change_pct": 0.0, "volume": 1_000_000},
    {"ticker": "MSFT", "price": 50.0, "change_pct": 0.0, "volume": 1_000_000},
    {"ticker": "NEW", "price": 50.0, "change_pct": 0.0, "volume": 1_000_000},
]


def _d(action, ticker, qty=5):
    return {"action": action, "ticker": ticker, "quantity": qty, "reasoning": "x", "confidence": 0.8}


def _broker():
    b = MagicMock()
    b.place_order = AsyncMock(return_value={"order_id": "o", "status": "accepted",
                                            "filled_qty": 0, "stop_order_id": "leg"})
    b.get_order = AsyncMock(return_value={"status": "held", "filled_qty": 0.0, "filled_avg_price": None})
    b.cancel_order = AsyncMock(return_value="canceled")
    b.place_stop_order = AsyncMock(return_value={"order_id": "s", "status": "new"})
    return b


async def _run(db, plan, decisions, b):
    from app.plans.executor import run_plan_cycle
    with patch("app.plans.executor.claude_brain.get_trade_decision",
               new_callable=AsyncMock, return_value=decisions) as claude, \
         patch("app.plans.executor.broker", b), \
         patch("app.plans.limits.notifier.notify_risk_event", new_callable=AsyncMock), \
         patch("app.plans.executor.notifier.notify_risk_event", new_callable=AsyncMock):
        results = await run_plan_cycle(db, plan, [], {}, _QUOTES, [], "", "", "")
    return results, claude


def _hold(db, plan, ticker, qty=10.0, price=50.0, ts=None):
    t = Trade(portfolio_id=plan.id, ticker=ticker, action="buy", quantity=qty, price=price,
              executed=True, guardrail_passed=True,
              timestamp=ts or datetime(2026, 1, 5, 15, 0))
    db.add(t)
    db.commit()


@pytest.mark.integration
class TestLimitsInCycle:
    async def test_hard_stop_switches_off_and_places_nothing(self, db_session):
        plan = _make_rules_portfolio(db_session, "claude_decides")
        plan.virtual_cash = 8_000.0  # budget 10,000 → -20%
        db_session.commit()
        b = _broker()
        results, claude = await _run(db_session, plan, [_d("buy", "MSFT")], b)

        assert results == []
        claude.assert_not_awaited()
        b.place_order.assert_not_awaited()
        db_session.refresh(plan)
        assert plan.is_active is False

    async def test_daily_halt_blocks_buy_not_sell(self, db_session):
        plan = _make_rules_portfolio(db_session, "claude_decides")
        _hold(db_session, plan, "AAPL")
        plan.virtual_cash = 9_100.0  # + 10 AAPL @ $50 = $9,600 → -4% vs yesterday
        db_session.add(PlanSnapshot(portfolio_id=plan.id, date=today_et() - timedelta(days=1),
                                    budget=10_000, virtual_cash=10_000, invested_value=0,
                                    total_value=10_000, pnl=0, pnl_pct=0))
        db_session.commit()
        b = _broker()
        results, _ = await _run(db_session, plan, [_d("buy", "MSFT"), _d("sell", "AAPL", 10)], b)

        buy, sell = results
        assert buy["action"] == "hold" and buy["reasoning"].startswith("Daily loss halt")
        assert sell["executed"] is True
        assert [c.kwargs["action"] for c in b.place_order.await_args_list] == ["sell"]

    async def test_third_buy_same_day_blocked(self, db_session):
        plan = _make_rules_portfolio(db_session, "claude_decides")
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        _hold(db_session, plan, "AAPL", qty=1, ts=now - timedelta(minutes=2))
        _hold(db_session, plan, "MSFT", qty=1, ts=now - timedelta(minutes=1))
        b = _broker()
        results, _ = await _run(db_session, plan, [_d("buy", "NEW")], b)

        assert results[0]["action"] == "hold"
        assert results[0]["reasoning"].startswith("Max new buys")
        b.place_order.assert_not_awaited()

    async def test_ninth_holding_blocked_in_cycle(self, db_session):
        plan = _make_rules_portfolio(db_session, "claude_decides")
        for i in range(8):
            _hold(db_session, plan, f"T{i}", qty=1, price=50.0)
        b = _broker()
        results, _ = await _run(db_session, plan, [_d("buy", "NEW")], b)

        assert results[0]["reasoning"].startswith("Max holdings")
        b.place_order.assert_not_awaited()

    async def test_prompt_max_positions_is_eight(self, db_session):
        plan = _make_rules_portfolio(db_session, "claude_decides")
        _, claude = await _run(db_session, plan, [_d("hold", "AAPL", 0)], _broker())
        assert claude.await_args.kwargs["guardrails_config"]["max_positions"] == 8


@pytest.mark.integration
class TestReviewFixes:
    async def test_buy_count_includes_this_cycles_buys(self, db_session):
        """Three buys proposed in one cycle → the third is blocked by buys made seconds earlier."""
        plan = _make_rules_portfolio(db_session, "claude_decides")
        b = _broker()
        results, _ = await _run(db_session, plan,
                                [_d("buy", "AAPL"), _d("buy", "MSFT"), _d("buy", "NEW")], b)
        assert [r["executed"] for r in results] == [True, True, False]
        assert results[2]["reasoning"].startswith("Max new buys")

    async def test_add_to_held_stock_allowed_at_eight_in_cycle(self, db_session):
        plan = _make_rules_portfolio(db_session, "claude_decides")
        for t in ["AAPL", "T1", "T2", "T3", "T4", "T5", "T6", "T7"]:
            _hold(db_session, plan, t, qty=1, price=50.0)
        b = _broker()
        results, _ = await _run(db_session, plan, [_d("buy", "AAPL")], b)
        assert results[0]["executed"] is True

    async def test_inactive_portfolio_stops_still_reconciled(self, db_session):
        """A hard-stopped (inactive) portfolio's broker stop fires → run_all_plans records it."""
        from app.plans.executor import run_all_plans
        plan = _make_rules_portfolio(db_session, "claude_decides")
        db_session.add(Trade(portfolio_id=plan.id, ticker="AAPL", action="buy", quantity=10,
                             price=50.0, executed=True, guardrail_passed=True, stop_price=46.0,
                             stop_qty=10, stop_order_id="leg-1", stop_state="open"))
        plan.is_active = False
        plan.virtual_cash = 9_500.0
        db_session.commit()
        b = _broker()
        b.get_positions = AsyncMock(return_value=[])
        b.get_account_balance = AsyncMock(return_value={"cash_available": 0, "total_value": 0})
        b.get_order = AsyncMock(return_value={"status": "filled", "filled_qty": 10.0, "filled_avg_price": 46.0})
        with patch("app.plans.executor.broker", b), \
             patch("app.plans.stops.notifier.notify_risk_event", new_callable=AsyncMock):
            await run_all_plans(db_session)

        db_session.refresh(plan)
        assert float(plan.virtual_cash) == 9_960.0
        assert db_session.query(Trade).filter_by(portfolio_id=plan.id, action="sell").count() == 1


class TestAccountBreakerRetired:
    async def test_account_drawdown_does_not_switch_off_portfolios(self, db_session):
        """Charter §3 limits are per strategy. A bad day in the whole Alpaca account
        (incl. positions no portfolio owns) must not switch the strategies off."""
        from datetime import date
        from app.models import PortfolioSnapshot
        from app.plans.executor import run_all_plans
        plan = _make_rules_portfolio(db_session, "claude_decides")
        today = date.today()
        for d, eq in ((today - timedelta(days=2), 100_000), (today - timedelta(days=1), 100_000)):
            db_session.add(PortfolioSnapshot(date=d, total_equity=eq, cash=0, invested=eq, unrealized_pnl=0))
        db_session.commit()
        b = _broker()
        b.get_positions = AsyncMock(return_value=[])
        b.get_account_balance = AsyncMock(return_value={"cash_available": 0, "total_value": 92_000})
        with patch("app.plans.executor.broker", b), \
             patch("app.plans.executor.fetch_market_data", new_callable=AsyncMock,
                   return_value=([], {}, [], [], "", "", "", "")), \
             patch("app.plans.executor.run_plan_cycle", new_callable=AsyncMock, return_value=[]) as cycle:
            await run_all_plans(db_session)

        db_session.refresh(plan)
        assert plan.is_active is True
        cycle.assert_awaited_once()
