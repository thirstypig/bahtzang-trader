"""Live cost recording: spread + sell fees on every executed trade, Claude API cost
per portfolio, fees on broker stop fills, and an audit row for a hard stop."""

import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.models import ApiUsage, Trade
from tests.test_executor_decision_modes import _make_rules_portfolio

_QUOTES = [{"ticker": "AAPL", "price": 50.0, "change_pct": 0.0, "volume": 1_000_000}]


def _d(action, qty):
    return [{"action": action, "ticker": "AAPL", "quantity": qty, "reasoning": "x", "confidence": 0.8}]


def _broker(bid=49.98, ask=50.02):
    b = MagicMock()
    b.place_order = AsyncMock(return_value={"order_id": "o", "status": "accepted",
                                            "filled_qty": 0, "stop_order_id": "leg"})
    b.get_order = AsyncMock(return_value={"status": "held", "filled_qty": 0.0, "filled_avg_price": None})
    b.cancel_order = AsyncMock(return_value="canceled")
    b.place_stop_order = AsyncMock(return_value={"order_id": "s", "status": "new"})
    b.get_bid_ask = AsyncMock(return_value=(bid, ask))
    return b


async def _run(db, plan, decisions, b, claude_side_effect=None):
    from app.plans.executor import run_plan_cycle
    mock = AsyncMock(return_value=decisions, side_effect=claude_side_effect)
    with patch("app.plans.executor.claude_brain.get_trade_decision", mock), \
         patch("app.plans.executor.broker", b), \
         patch("app.plans.stops.notifier.notify_risk_event", new_callable=AsyncMock), \
         patch("app.plans.limits.notifier.notify_risk_event", new_callable=AsyncMock), \
         patch("app.plans.executor.notifier.notify_risk_event", new_callable=AsyncMock):
        return await run_plan_cycle(db, plan, [], {}, _QUOTES, [], "", "", "")


def _seed(db, plan, qty=10.0):
    db.add(Trade(portfolio_id=plan.id, ticker="AAPL", action="buy", quantity=qty, price=50.0,
                 executed=True, guardrail_passed=True))
    plan.virtual_cash = float(plan.virtual_cash) - qty * 50.0
    db.commit()


@pytest.mark.integration
class TestTradeCosts:
    async def test_buy_records_spread(self, db_session):
        plan = _make_rules_portfolio(db_session, "claude_decides")
        results = await _run(db_session, plan, _d("buy", 5), _broker())
        row = db_session.get(Trade, results[0]["trade_id"])
        # risk engine sizes 25 sh; half of $0.04 × 25 = $0.50
        assert float(row.spread_cost) == pytest.approx(0.50)
        assert row.fee_cost is None

    async def test_sell_records_spread_and_fee(self, db_session):
        plan = _make_rules_portfolio(db_session, "claude_decides")
        _seed(db_session, plan)
        results = await _run(db_session, plan, _d("sell", 10), _broker())
        row = db_session.get(Trade, results[0]["trade_id"])
        assert float(row.spread_cost) == pytest.approx(0.20)
        assert float(row.fee_cost) == pytest.approx(500 * 20.60 / 1e6 + 10 * 0.000195)

    async def test_missing_quote_records_null_spread(self, db_session):
        plan = _make_rules_portfolio(db_session, "claude_decides")
        results = await _run(db_session, plan, _d("buy", 5), _broker(bid=None, ask=None))
        assert db_session.get(Trade, results[0]["trade_id"]).spread_cost is None


@pytest.mark.integration
class TestApiUsage:
    async def test_decision_usage_recorded_per_portfolio(self, db_session):
        plan = _make_rules_portfolio(db_session, "claude_decides")
        usage = SimpleNamespace(input_tokens=1000, output_tokens=500,
                                cache_read_input_tokens=0, cache_creation_input_tokens=0)

        async def claude(*args, usage_sink=None, **kw):
            usage_sink.append(usage)
            return _d("hold", 0)

        await _run(db_session, plan, None, _broker(), claude_side_effect=claude)
        rows = db_session.query(ApiUsage).filter_by(portfolio_id=plan.id).all()
        assert len(rows) == 1
        assert rows[0].purpose == "decision"
        assert (rows[0].input_tokens, rows[0].output_tokens) == (1000, 500)
        assert float(rows[0].cost) == pytest.approx(0.0105)

    async def test_missing_usage_records_nothing(self, db_session):
        plan = _make_rules_portfolio(db_session, "claude_decides")
        await _run(db_session, plan, _d("hold", 0), _broker())
        assert db_session.query(ApiUsage).count() == 0


@pytest.mark.integration
class TestStopAndHardStop:
    async def test_stop_fill_records_fee(self, db_session):
        from app.plans.stops import reconcile_stops
        from tests.conftest import make_plan
        plan = make_plan(db_session, virtual_cash=500.0)
        db_session.add(Trade(portfolio_id=plan.id, ticker="AAPL", action="buy", quantity=10,
                             price=50.0, executed=True, guardrail_passed=True, stop_price=46.0,
                             stop_qty=10, stop_order_id="leg-1", stop_state="open"))
        db_session.commit()
        b = _broker()
        b.get_order = AsyncMock(return_value={"status": "filled", "filled_qty": 10.0, "filled_avg_price": 46.0})
        with patch("app.plans.stops.notifier.notify_risk_event", new_callable=AsyncMock):
            sells = await reconcile_stops(db_session, plan, b)
        assert float(sells[0].fee_cost) == pytest.approx(460 * 20.60 / 1e6 + 10 * 0.000195)
        assert sells[0].spread_cost is None

    async def test_hard_stop_writes_audit_row(self, db_session):
        plan = _make_rules_portfolio(db_session, "claude_decides")
        plan.virtual_cash = 8_000.0
        db_session.commit()
        await _run(db_session, plan, _d("buy", 5), _broker())
        row = db_session.query(Trade).filter_by(portfolio_id=plan.id).one()
        assert row.action == "hold" and row.claude_reasoning.startswith("HARD STOP")
