"""Weekly report (charter §5): per portfolio + account, week and since start, return
vs SPY before and after costs, trades, costs, safety-limit events, Claude draft note.

Fixed week: Mon 2026-11-02 … Fri 2026-11-06 (ET). Previous Friday = 2026-10-30.
"""

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.models import ApiUsage, Trade
from app.plans.models import PlanSnapshot
from tests.conftest import make_plan

FRI = date(2026, 11, 6)
SPY = {date(2026, 10, 1): 480.0, date(2026, 10, 30): 500.0, date(2026, 11, 6): 505.0}


def _snap(db, plan, d, value):
    db.add(PlanSnapshot(portfolio_id=plan.id, date=d, budget=plan.budget,
                        virtual_cash=value, invested_value=0, total_value=value,
                        pnl=0, pnl_pct=0))


def _trade(db, plan, ts, action, qty, price, **kw):
    t = Trade(portfolio_id=plan.id, ticker=kw.pop("ticker", "AAPL"), action=action,
              quantity=qty, price=price, executed=kw.pop("executed", True),
              guardrail_passed=True, timestamp=ts, **kw)
    db.add(t)
    return t


def _plan(db):
    p = make_plan(db, name="Pool A Claude", budget=10_000, virtual_cash=10_000)
    p.created_at = datetime(2026, 10, 1, 14, 0, tzinfo=timezone.utc)
    db.commit()
    return p


def _row(payload, plan):
    return next(r for r in payload["portfolios"] if r["id"] == plan.id)


@pytest.mark.integration
class TestBuildWeeklyReport:
    def test_return_vs_spy_before_and_after_costs(self, db_session):
        from app.reports.engine import build_weekly_report
        plan = _plan(db_session)
        _snap(db_session, plan, date(2026, 10, 30), 10_000)
        _snap(db_session, plan, FRI, 10_300)
        _trade(db_session, plan, datetime(2026, 10, 20, 15), "buy", 10, 100.0)   # before the week
        _trade(db_session, plan, datetime(2026, 11, 3, 15), "buy", 10, 100.0, spread_cost=0.5)
        _trade(db_session, plan, datetime(2026, 11, 5, 15), "sell", 10, 120.0, spread_cost=0.2, fee_cost=0.01)
        db_session.add(ApiUsage(portfolio_id=plan.id, purpose="decision", model="m",
                                timestamp=datetime(2026, 11, 3, 15, tzinfo=timezone.utc), cost=0.10))
        db_session.commit()

        r = _row(build_weekly_report(db_session, FRI, SPY), plan)

        assert r["return_pct"] == pytest.approx(3.0)
        assert r["spy_return_pct"] == pytest.approx(1.0)
        # avg cost 100 → sell 10 @ 120 realizes $200 → tax $48
        c = r["costs"]
        assert (c["spread"], c["fees"], c["api"], c["est_tax"]) == pytest.approx((0.7, 0.01, 0.10, 48.0))
        # Paper fills already happen at the bid/ask (verified 2026-11-09), so the
        # spread is shown but NOT subtracted again.
        assert c["spread_in_fills"] is True
        assert c["total"] == pytest.approx(0.01 + 0.10 + 48)
        assert r["after_cost_return_pct"] == pytest.approx((300 - 0.01 - 0.10 - 48) / 100)
        assert r["beat_spy"] is True
        assert (r["trades"], r["wins"], r["losses"]) == (2, 1, 0)

    def test_empty_week_report(self, db_session):
        from app.reports.engine import build_weekly_report
        plan = _plan(db_session)
        r = _row(build_weekly_report(db_session, FRI, SPY), plan)
        assert r["return_pct"] == 0 and r["trades"] == 0 and r["costs"]["total"] == 0

    def test_unpriced_spread_reported(self, db_session):
        from app.reports.engine import build_weekly_report
        plan = _plan(db_session)
        _trade(db_session, plan, datetime(2026, 11, 3, 15), "buy", 1, 100.0, spread_cost=None)
        db_session.commit()
        assert _row(build_weekly_report(db_session, FRI, SPY), plan)["costs"]["spread_unpriced_trades"] == 1

    def test_limit_events_counted(self, db_session):
        from app.reports.engine import build_weekly_report
        plan = _plan(db_session)
        for reason in ["Daily loss halt: down 3.4%", "Daily loss halt: down 3.6%", "Max holdings: 8 held"]:
            _trade(db_session, plan, datetime(2026, 11, 4, 15), "hold", 0, None,
                   executed=False, claude_reasoning=reason)
        db_session.commit()
        events = {e["type"]: e["count"] for e in _row(build_weekly_report(db_session, FRI, SPY), plan)["limit_events"]}
        assert events == {"Daily loss halt": 2, "Max holdings": 1}

    def test_since_start_uses_budget(self, db_session):
        from app.reports.engine import build_weekly_report
        plan = _plan(db_session)
        _snap(db_session, plan, FRI, 10_500)
        db_session.commit()
        s = _row(build_weekly_report(db_session, FRI, SPY), plan)["since_start"]
        assert s["return_pct"] == pytest.approx(5.0)
        assert s["spy_return_pct"] == pytest.approx((505 / 480 - 1) * 100, abs=1e-3)  # rounded to 4 dp

    def test_account_row_sums_portfolios(self, db_session):
        from app.reports.engine import build_weekly_report
        a = _plan(db_session)
        b = make_plan(db_session, name="B", budget=5_000, virtual_cash=5_000)
        b.created_at = a.created_at
        _snap(db_session, a, date(2026, 10, 30), 10_000); _snap(db_session, a, FRI, 10_300)
        _snap(db_session, b, date(2026, 10, 30), 5_000); _snap(db_session, b, FRI, 4_900)
        db_session.commit()
        acct = build_weekly_report(db_session, FRI, SPY)["account"]
        assert (acct["start_value"], acct["end_value"]) == (15_000, 15_200)


@pytest.mark.integration
class TestRunWeeklyReport:
    async def _run(self, db, note_side_effect=None):
        from app.reports.engine import run_weekly_report
        note = AsyncMock(return_value=("Draft: keep rules as they are.", None),
                         side_effect=note_side_effect)
        with patch("app.reports.engine._spy_closes", new=AsyncMock(return_value=SPY)), \
             patch("app.reports.engine._draft_note", new=note):
            return await run_weekly_report(db, FRI)

    async def test_rerun_replaces_week(self, db_session):
        from app.reports.models import WeeklyReport
        _plan(db_session)
        await self._run(db_session)
        await self._run(db_session)
        assert db_session.query(WeeklyReport).filter_by(week_ending=FRI).count() == 1

    async def test_note_failure_still_saves(self, db_session):
        _plan(db_session)
        rep = await self._run(db_session, note_side_effect=RuntimeError("api down"))
        assert rep.note is None and rep.payload["portfolios"]


@pytest.mark.integration
class TestRoutes:
    async def test_routes_list_and_detail(self, client, db_session):
        from app.reports.models import WeeklyReport
        db_session.add(WeeklyReport(week_ending=FRI, payload={"week_ending": "2026-11-06",
                                    "portfolios": [], "account": {}}, note="n"))
        db_session.commit()
        lst = client.get("/reports").json()
        assert lst[0]["week_ending"] == "2026-11-06"
        detail = client.get(f"/reports/{lst[0]['id']}").json()
        assert detail["note"] == "n"


@pytest.mark.integration
class TestReviewFixes:
    def test_switched_off_portfolio_still_reported(self, db_session):
        """A hard-stopped portfolio with no snapshot/trade this week must not vanish."""
        from app.reports.engine import build_weekly_report
        plan = _plan(db_session)
        _trade(db_session, plan, datetime(2026, 10, 20, 15), "buy", 10, 100.0,
               virtual_cash_before=10_000, virtual_cash_after=9_000)
        _trade(db_session, plan, datetime(2026, 10, 28, 15), "sell", 10, 80.0,
               virtual_cash_before=9_000, virtual_cash_after=9_800)
        _snap(db_session, plan, date(2026, 10, 30), 9_800)
        plan.is_active = False
        db_session.commit()

        payload = build_weekly_report(db_session, FRI, SPY)
        r = _row(payload, plan)
        assert r["end_value"] == 9_800 and r["since_start"]["return_pct"] == pytest.approx(-2.0)
        assert payload["account"]["since_start_value"] == 10_000

    def test_no_snapshot_flat_cash_uses_ledger_cash(self, db_session):
        """No positions and no snapshot this week: end value = cash after the last trade."""
        from app.reports.engine import build_weekly_report
        plan = _plan(db_session)
        _snap(db_session, plan, date(2026, 10, 30), 10_000)
        _trade(db_session, plan, datetime(2026, 10, 20, 15), "buy", 10, 100.0,
               virtual_cash_before=10_000, virtual_cash_after=9_000)
        _trade(db_session, plan, datetime(2026, 11, 4, 15), "sell", 10, 95.0,
               virtual_cash_before=9_000, virtual_cash_after=9_950)
        db_session.commit()
        assert _row(build_weekly_report(db_session, FRI, SPY), plan)["end_value"] == 9_950

    def test_account_tax_nets_gains_across_portfolios(self, db_session):
        from app.reports.engine import build_weekly_report
        a = _plan(db_session)
        b = make_plan(db_session, name="B", budget=5_000, virtual_cash=5_000)
        b.created_at = a.created_at
        for p, sell_px in ((a, 110.0), (b, 90.0)):  # +$100 and -$100 realized
            _trade(db_session, p, datetime(2026, 11, 2, 15), "buy", 10, 100.0)
            _trade(db_session, p, datetime(2026, 11, 4, 15), "sell", 10, sell_px)
        db_session.commit()
        acct = build_weekly_report(db_session, FRI, SPY)["account"]
        assert acct["costs"]["est_tax"] == 0

    def test_account_includes_unassigned_api_cost(self, db_session):
        from app.reports.engine import build_weekly_report
        _plan(db_session)
        db_session.add(ApiUsage(portfolio_id=None, purpose="report_note", model="m",
                                timestamp=datetime(2026, 11, 6, 21, tzinfo=timezone.utc), cost=0.05))
        db_session.commit()
        assert build_weekly_report(db_session, FRI, SPY)["account"]["costs"]["api"] == pytest.approx(0.05)
