"""Unit tests for the plan executor — virtual cash, positions, sell validation."""

import pytest
from tests.conftest import make_plan, make_trade
from app.plans.executor import compute_virtual_positions


@pytest.mark.unit
class TestComputeVirtualPositions:
    """compute_virtual_positions aggregates net shares from executed trades."""

    def test_empty_plan(self, db_session):
        plan = make_plan(db_session)
        positions = compute_virtual_positions(db_session, plan.id)
        assert positions == {}

    def test_single_buy(self, db_session):
        plan = make_plan(db_session)
        make_trade(db_session, plan.id, ticker="AAPL", action="buy", quantity=10)
        positions = compute_virtual_positions(db_session, plan.id)
        assert positions == {"AAPL": 10.0}

    def test_buy_then_sell(self, db_session):
        plan = make_plan(db_session)
        make_trade(db_session, plan.id, ticker="AAPL", action="buy", quantity=10)
        make_trade(db_session, plan.id, ticker="AAPL", action="sell", quantity=3)
        positions = compute_virtual_positions(db_session, plan.id)
        assert positions == {"AAPL": 7.0}

    def test_full_sell_removes_ticker(self, db_session):
        plan = make_plan(db_session)
        make_trade(db_session, plan.id, ticker="AAPL", action="buy", quantity=5)
        make_trade(db_session, plan.id, ticker="AAPL", action="sell", quantity=5)
        positions = compute_virtual_positions(db_session, plan.id)
        # Net zero — ticker should not appear
        assert "AAPL" not in positions

    def test_multiple_tickers(self, db_session):
        plan = make_plan(db_session)
        make_trade(db_session, plan.id, ticker="AAPL", action="buy", quantity=10)
        make_trade(db_session, plan.id, ticker="TSLA", action="buy", quantity=5)
        make_trade(db_session, plan.id, ticker="AAPL", action="sell", quantity=2)
        positions = compute_virtual_positions(db_session, plan.id)
        assert positions == {"AAPL": 8.0, "TSLA": 5.0}

    def test_ignores_unexecuted_trades(self, db_session):
        plan = make_plan(db_session)
        make_trade(db_session, plan.id, ticker="AAPL", action="buy", quantity=10)
        make_trade(
            db_session, plan.id, ticker="AAPL", action="buy", quantity=100,
            executed=False, guardrail_passed=False,
            guardrail_block_reason="Insufficient cash",
        )
        positions = compute_virtual_positions(db_session, plan.id)
        assert positions == {"AAPL": 10.0}

    def test_cross_plan_isolation(self, db_session):
        """Plans should not see each other's positions."""
        plan_a = make_plan(db_session, name="Plan A")
        plan_b = make_plan(db_session, name="Plan B")
        make_trade(db_session, plan_a.id, ticker="AAPL", action="buy", quantity=10)
        make_trade(db_session, plan_b.id, ticker="TSLA", action="buy", quantity=5)

        pos_a = compute_virtual_positions(db_session, plan_a.id)
        pos_b = compute_virtual_positions(db_session, plan_b.id)
        assert pos_a == {"AAPL": 10.0}
        assert pos_b == {"TSLA": 5.0}

    def test_fractional_shares(self, db_session):
        plan = make_plan(db_session)
        make_trade(db_session, plan.id, ticker="AAPL", action="buy", quantity=0.5)
        make_trade(db_session, plan.id, ticker="AAPL", action="buy", quantity=0.25)
        positions = compute_virtual_positions(db_session, plan.id)
        assert positions["AAPL"] == pytest.approx(0.75)


@pytest.mark.unit
class TestPlanToGuardrailsConfig:
    """_plan_to_guardrails_config converts plan settings to guardrails dict."""

    def test_basic_config(self, db_session):
        from app.plans.executor import _plan_to_guardrails_config
        plan = make_plan(db_session, budget=5000, risk_profile="moderate")
        config = _plan_to_guardrails_config(plan)
        assert config["max_total_invested"] == 5000
        assert config["trading_goal"] == "maximize_returns"
        assert config["trading_frequency"] == "1x"
        assert config["kill_switch"] is False

    def test_single_trade_capped_at_half_budget(self, db_session):
        from app.plans.executor import _plan_to_guardrails_config
        plan = make_plan(db_session, budget=1000)
        config = _plan_to_guardrails_config(plan)
        assert config["max_single_trade_size"] <= 500

    def test_target_included_when_set(self, db_session):
        from app.plans.executor import _plan_to_guardrails_config
        plan = make_plan(
            db_session, target_amount=10000, target_date="2027-01-01",
        )
        config = _plan_to_guardrails_config(plan)
        assert config["target_amount"] == 10000
        assert config["target_date"] == "2027-01-01"

    def test_no_target_when_not_set(self, db_session):
        from app.plans.executor import _plan_to_guardrails_config
        plan = make_plan(db_session)
        config = _plan_to_guardrails_config(plan)
        assert "target_amount" not in config
        assert "target_date" not in config
