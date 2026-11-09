"""Broker-held stop lifecycle against the virtual ledger (app/plans/stops.py).

A stop that fires at Alpaca between cycles sells real shares; the ledger must catch up
before anything else reads positions, or the next cycle "sells" shares that are gone
(and, in a shared account, Alpaca sells another portfolio's or an orphan's shares).
"""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from app.models import Trade
from tests.conftest import make_plan


def _broker(**status_by_id):
    """Fake broker whose get_order answers from a {order_id: dict} map."""
    b = MagicMock()

    async def get_order(oid):
        v = status_by_id[oid]
        if isinstance(v, Exception):
            raise v
        return v

    b.get_order = AsyncMock(side_effect=get_order)
    b.cancel_order = AsyncMock(return_value="canceled")
    b.place_stop_order = AsyncMock(return_value={"order_id": "stop-new", "status": "new"})
    return b


def _open_buy(db, plan, ticker="AAPL", qty=10.0, price=50.0, stop=46.0, leg="leg-1"):
    t = Trade(
        portfolio_id=plan.id, ticker=ticker, action="buy", quantity=qty, price=price,
        executed=True, guardrail_passed=True, stop_price=stop, stop_order_id=leg,
        stop_state="open",
    )
    db.add(t)
    db.commit()
    return t


def _filled(qty=10.0, px=46.0):
    return {"status": "filled", "filled_qty": qty, "filled_avg_price": px}


@pytest.fixture
def slack():
    with patch("app.plans.stops.notifier.notify_risk_event", new_callable=AsyncMock) as m:
        yield m


@pytest.mark.integration
class TestReconcileStops:
    async def test_filled_stop_inserts_sell_and_credits_cash(self, db_session, slack):
        from app.plans.stops import reconcile_stops
        plan = make_plan(db_session, virtual_cash=500.0)
        buy = _open_buy(db_session, plan)

        inserted = await reconcile_stops(db_session, plan, _broker(**{"leg-1": _filled()}))

        assert len(inserted) == 1
        sell = inserted[0]
        assert (sell.action, sell.quantity, float(sell.price)) == ("sell", 10.0, 46.0)
        assert sell.executed and sell.alpaca_order_id == "leg-1"
        assert sell.claude_reasoning.startswith("Broker stop fired")
        assert float(sell.virtual_cash_before) == 500.0
        assert float(sell.virtual_cash_after) == 960.0
        db_session.refresh(plan)
        db_session.refresh(buy)
        assert float(plan.virtual_cash) == 960.0
        assert buy.stop_state == "filled"
        slack.assert_awaited_once()

    @pytest.mark.parametrize("status", ["held", "new", "accepted"])
    async def test_open_stop_untouched(self, db_session, slack, status):
        from app.plans.stops import reconcile_stops
        plan = make_plan(db_session)
        buy = _open_buy(db_session, plan)
        b = _broker(**{"leg-1": {"status": status, "filled_qty": 0.0, "filled_avg_price": None}})

        assert await reconcile_stops(db_session, plan, b) == []
        db_session.refresh(buy)
        assert buy.stop_state == "open"
        slack.assert_not_awaited()

    async def test_externally_cancelled_stop_flags_unprotected(self, db_session, slack):
        from app.plans.stops import reconcile_stops
        plan = make_plan(db_session)
        buy = _open_buy(db_session, plan)
        b = _broker(**{"leg-1": {"status": "canceled", "filled_qty": 0.0, "filled_avg_price": None}})

        assert await reconcile_stops(db_session, plan, b) == []
        db_session.refresh(buy)
        assert buy.stop_state == "cancelled"
        assert "UNPROTECTED" in slack.await_args.args[0]

    async def test_reconcile_is_idempotent(self, db_session, slack):
        from app.plans.stops import reconcile_stops
        plan = make_plan(db_session, virtual_cash=500.0)
        _open_buy(db_session, plan)
        b = _broker(**{"leg-1": _filled()})

        await reconcile_stops(db_session, plan, b)
        await reconcile_stops(db_session, plan, b)

        sells = db_session.query(Trade).filter_by(portfolio_id=plan.id, action="sell").count()
        assert sells == 1

    async def test_broker_error_leaves_state_open(self, db_session, slack):
        from app.plans.stops import reconcile_stops
        plan = make_plan(db_session)
        buy = _open_buy(db_session, plan)

        assert await reconcile_stops(db_session, plan, _broker(**{"leg-1": RuntimeError("down")})) == []
        db_session.refresh(buy)
        assert buy.stop_state == "open"

    async def test_other_portfolios_stops_ignored(self, db_session, slack):
        from app.plans.stops import reconcile_stops
        a = make_plan(db_session, name="A")
        b_plan = make_plan(db_session, name="B")
        _open_buy(db_session, b_plan, leg="leg-b")
        b = _broker(**{"leg-b": _filled()})

        assert await reconcile_stops(db_session, a, b) == []
        b.get_order.assert_not_awaited()


@pytest.mark.integration
class TestReleaseStops:
    async def test_sell_cancels_only_own_stop_first(self, db_session, slack):
        from app.plans.stops import release_stops
        a = make_plan(db_session, name="A")
        b_plan = make_plan(db_session, name="B")
        mine = _open_buy(db_session, a, leg="leg-a", stop=46.0)
        theirs = _open_buy(db_session, b_plan, leg="leg-b", stop=44.0)
        b = _broker()

        ok, prior = await release_stops(db_session, a, "AAPL", b)

        assert (ok, prior) == (True, 46.0)
        b.cancel_order.assert_awaited_once_with("leg-a")
        db_session.refresh(mine)
        db_session.refresh(theirs)
        assert mine.stop_state == "cancelled"
        assert theirs.stop_state == "open"

    async def test_highest_stop_kept_across_adds(self, db_session, slack):
        from app.plans.stops import release_stops
        plan = make_plan(db_session)
        _open_buy(db_session, plan, leg="leg-1", stop=46.0)
        _open_buy(db_session, plan, leg="leg-2", stop=48.5)

        ok, prior = await release_stops(db_session, plan, "AAPL", _broker())
        assert (ok, prior) == (True, 48.5)

    async def test_cancel_race_records_fill_and_blocks_sell(self, db_session, slack):
        from app.plans.stops import release_stops
        plan = make_plan(db_session, virtual_cash=500.0)
        _open_buy(db_session, plan)
        b = _broker(**{"leg-1": _filled()})
        b.cancel_order = AsyncMock(return_value="filled")

        ok, prior = await release_stops(db_session, plan, "AAPL", b)

        assert (ok, prior) == (False, None)
        sell = db_session.query(Trade).filter_by(portfolio_id=plan.id, action="sell").one()
        assert sell.claude_reasoning.startswith("Broker stop fired")

    async def test_no_open_stops_ok(self, db_session, slack):
        from app.plans.stops import release_stops
        plan = make_plan(db_session)
        b = _broker()
        assert await release_stops(db_session, plan, "AAPL", b) == (True, None)
        b.cancel_order.assert_not_awaited()


@pytest.mark.integration
class TestProtectRemainder:
    def _sell_row(self, db, plan):
        t = Trade(portfolio_id=plan.id, ticker="AAPL", action="sell", quantity=2.4,
                  price=55.0, executed=True, guardrail_passed=True)
        db.add(t)
        db.commit()
        return t

    async def test_protect_remainder_places_whole_share_stop(self, db_session, slack):
        from app.plans.stops import protect_remainder
        plan = make_plan(db_session)
        sell = self._sell_row(db_session, plan)
        b = _broker()

        await protect_remainder(db_session, plan, sell, 7.6, 46.0, b)

        b.place_stop_order.assert_awaited_once_with("AAPL", 7, 46.0)
        db_session.refresh(sell)
        assert (sell.stop_order_id, float(sell.stop_price), sell.stop_state) == ("stop-new", 46.0, "open")

    async def test_protect_remainder_under_one_share_warns(self, db_session, slack, caplog):
        from app.plans.stops import protect_remainder
        plan = make_plan(db_session)
        sell = self._sell_row(db_session, plan)
        b = _broker()

        await protect_remainder(db_session, plan, sell, 0.4, 46.0, b)

        b.place_stop_order.assert_not_awaited()
        assert "unprotected" in caplog.text.lower()

    async def test_protect_remainder_broker_failure_alerts(self, db_session, slack):
        from app.plans.stops import protect_remainder
        plan = make_plan(db_session)
        sell = self._sell_row(db_session, plan)
        b = _broker()
        b.place_stop_order = AsyncMock(side_effect=RuntimeError("rejected"))

        await protect_remainder(db_session, plan, sell, 7.0, 46.0, b)

        assert "UNPROTECTED" in slack.await_args.args[0]
