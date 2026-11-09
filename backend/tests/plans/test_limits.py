"""Charter §3 per-portfolio limits (app/plans/limits.py).

Fixed calendar: today = Wed 2026-11-11 (ET). Yesterday = Tue 11-10, this week's
Monday = 11-09, last Friday = 11-06.
"""

import pytest
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, patch

from app.models import Trade
from app.plans.models import PlanSnapshot
from tests.conftest import make_plan

TODAY = date(2026, 11, 11)
NOW = datetime(2026, 11, 11, 15, 0, tzinfo=timezone.utc)  # 10:00 AM ET


def _snap(db, plan, d, value):
    db.add(PlanSnapshot(portfolio_id=plan.id, date=d, budget=plan.budget,
                        virtual_cash=value, invested_value=0, total_value=value,
                        pnl=0, pnl_pct=0))
    db.commit()


def _buy(db, plan, ticker, ts):
    db.add(Trade(portfolio_id=plan.id, ticker=ticker, action="buy", quantity=1,
                 price=10, executed=True, guardrail_passed=True, timestamp=ts))
    db.commit()


def _plan(db):
    return make_plan(db, budget=10_000, virtual_cash=10_000)


class TestPortfolioValue:
    def test_portfolio_value_uses_price_then_avg_cost(self):
        from app.plans.limits import portfolio_value
        v = portfolio_value(1000, {"A": 10, "B": 5}, {"A": 20}, {"B": 30})
        assert v == 1350


@pytest.mark.integration
class TestCycleLimits:
    def test_no_snapshots_uses_budget(self, db_session):
        from app.plans.limits import evaluate_cycle_limits
        lim = evaluate_cycle_limits(db_session, _plan(db_session), 9_800, TODAY)
        assert (lim.hard_stop, lim.buy_halt) == (False, None)

    def test_daily_halt_vs_yesterday_snapshot(self, db_session):
        from app.plans.limits import evaluate_cycle_limits
        plan = _plan(db_session)
        _snap(db_session, plan, date(2026, 11, 10), 10_000)
        assert evaluate_cycle_limits(db_session, plan, 9_690, TODAY).buy_halt.startswith("Daily loss halt")
        assert evaluate_cycle_limits(db_session, plan, 9_710, TODAY).buy_halt is None

    def test_todays_snapshot_is_not_the_daily_reference(self, db_session):
        from app.plans.limits import evaluate_cycle_limits
        plan = _plan(db_session)
        _snap(db_session, plan, date(2026, 11, 10), 10_000)
        _snap(db_session, plan, TODAY, 9_000)  # e.g. a re-run after today's close
        assert evaluate_cycle_limits(db_session, plan, 9_690, TODAY).buy_halt.startswith("Daily loss halt")

    def test_weekly_halt_vs_last_week_snapshot(self, db_session):
        from app.plans.limits import evaluate_cycle_limits
        plan = _plan(db_session)
        _snap(db_session, plan, date(2026, 11, 6), 10_000)   # last Friday
        _snap(db_session, plan, date(2026, 11, 10), 9_400)   # yesterday — day is flat
        lim = evaluate_cycle_limits(db_session, plan, 9_390, TODAY)
        assert lim.buy_halt.startswith("Weekly loss halt")

    def test_hard_stop_at_15pct(self, db_session):
        from app.plans.limits import evaluate_cycle_limits
        plan = _plan(db_session)
        assert evaluate_cycle_limits(db_session, plan, 8_500, TODAY).hard_stop is True
        assert evaluate_cycle_limits(db_session, plan, 8_510, TODAY).hard_stop is False


@pytest.mark.integration
class TestBuyBlockReason:
    def _limits(self, halt=None):
        from app.plans.limits import CycleLimits
        return CycleLimits(hard_stop=False, buy_halt=halt)

    def test_halt_blocks_buy(self, db_session):
        from app.plans.limits import buy_block_reason
        r = buy_block_reason(db_session, _plan(db_session), "AAPL", {}, self._limits("Daily loss halt: x"), NOW)
        assert r.startswith("Daily loss halt")

    def test_ninth_new_holding_blocked(self, db_session):
        from app.plans.limits import buy_block_reason
        held = {f"T{i}": 1.0 for i in range(8)}
        r = buy_block_reason(db_session, _plan(db_session), "NEW", held, self._limits(), NOW)
        assert r.startswith("Max holdings")

    def test_add_to_existing_allowed_at_eight(self, db_session):
        from app.plans.limits import buy_block_reason
        held = {f"T{i}": 1.0 for i in range(8)}
        assert buy_block_reason(db_session, _plan(db_session), "T3", held, self._limits(), NOW) is None

    def test_two_buys_today_blocks_third(self, db_session):
        from app.plans.limits import buy_block_reason
        plan = _plan(db_session)
        _buy(db_session, plan, "A", datetime(2026, 11, 10, 20, 0))   # yesterday — doesn't count
        _buy(db_session, plan, "B", datetime(2026, 11, 11, 14, 30))  # 9:30 ET today
        assert buy_block_reason(db_session, plan, "C", {}, self._limits(), NOW) is None
        _buy(db_session, plan, "C", datetime(2026, 11, 11, 14, 45))
        r = buy_block_reason(db_session, plan, "D", {}, self._limits(), NOW)
        assert r.startswith("Max new buys")


@pytest.mark.integration
class TestSwitchOff:
    async def test_switch_off_deactivates_and_alerts(self, db_session):
        from app.plans.limits import switch_off
        plan = _plan(db_session)
        with patch("app.plans.limits.notifier.notify_risk_event", new_callable=AsyncMock) as alert:
            await switch_off(db_session, plan, 8_400)
        db_session.refresh(plan)
        assert plan.is_active is False
        assert "HARD STOP" in alert.await_args.args[0]
