"""Unit tests for Plan data models — creation, serialization, constraints."""

import pytest
from tests.conftest import make_plan, make_trade


@pytest.mark.unit
class TestPlanModel:
    def test_create_plan(self, db_session):
        plan = make_plan(db_session, name="Growth", budget=10000, virtual_cash=10000)
        assert plan.id is not None
        assert plan.name == "Growth"
        assert plan.budget == 10000.0
        assert plan.virtual_cash == 10000.0
        assert plan.is_active is True

    def test_plan_to_dict(self, db_session):
        plan = make_plan(db_session)
        d = plan.to_dict()
        assert d["name"] == "Test Plan"
        assert d["budget"] == 5000.0
        assert "id" in d
        assert "created_at" in d
        assert "updated_at" in d

    def test_plan_defaults(self, db_session):
        plan = make_plan(db_session)
        assert plan.risk_profile == "moderate"
        assert plan.trading_frequency == "1x"
        assert plan.target_amount is None
        assert plan.target_date is None


@pytest.mark.unit
class TestPlanTradeModel:
    def test_create_trade(self, db_session):
        plan = make_plan(db_session)
        trade = make_trade(db_session, plan.id)
        assert trade.id is not None
        assert trade.plan_id == plan.id
        assert trade.ticker == "AAPL"
        assert trade.executed is True

    def test_trade_to_dict(self, db_session):
        plan = make_plan(db_session)
        trade = make_trade(db_session, plan.id)
        d = trade.to_dict()
        assert d["ticker"] == "AAPL"
        assert d["action"] == "buy"
        assert d["quantity"] == 1.0
        assert d["price"] == 150.0
        assert d["guardrail_passed"] is True

    def test_trade_with_alpaca_order_id(self, db_session):
        plan = make_plan(db_session)
        trade = make_trade(db_session, plan.id, alpaca_order_id="abc-123")
        assert trade.alpaca_order_id == "abc-123"

    def test_trade_holds_tracked(self, db_session):
        """Hold decisions are logged but not executed."""
        plan = make_plan(db_session)
        trade = make_trade(
            db_session, plan.id,
            action="hold", ticker="", quantity=0, price=None,
            executed=False, guardrail_passed=True,
            virtual_cash_before=5000, virtual_cash_after=5000,
        )
        assert trade.executed is False
        assert trade.action == "hold"
