"""Tests for the unified Trade model (067-fix) and Numeric money fields (071-fix).

These tests verify:
- Trade works with and without plan_id (unified model)
- to_dict() conditionally includes plan fields
- Decimal/Numeric money fields roundtrip correctly
- Plan trade counts use the unified table
"""

import pytest
from decimal import Decimal
from tests.conftest import make_plan, make_trade
from app.models import Trade


@pytest.mark.unit
class TestUnifiedTradeModel:
    """067-fix: Trade table handles both global and plan-scoped trades."""

    def test_create_global_trade(self, db_session):
        """Legacy trade with no plan_id should work."""
        trade = Trade(
            ticker="AAPL", action="buy", quantity=10,
            price=Decimal("150.00"), guardrail_passed=True, executed=True,
        )
        db_session.add(trade)
        db_session.commit()
        db_session.refresh(trade)
        assert trade.id is not None
        assert trade.plan_id is None
        assert trade.alpaca_order_id is None
        assert trade.virtual_cash_before is None

    def test_create_plan_trade(self, db_session):
        """Plan trade with plan_id and virtual cash tracking."""
        plan = make_plan(db_session)
        trade = make_trade(db_session, plan.id)
        assert trade.plan_id == plan.id
        assert trade.virtual_cash_before is not None
        assert trade.virtual_cash_after is not None

    def test_to_dict_global_trade_excludes_plan_fields(self, db_session):
        """Global trades should not include plan_id/virtual_cash in dict."""
        trade = Trade(
            ticker="TSLA", action="hold", quantity=0,
            price=None, guardrail_passed=True, executed=False,
        )
        db_session.add(trade)
        db_session.commit()
        db_session.refresh(trade)
        d = trade.to_dict()
        assert "plan_id" not in d
        assert "virtual_cash_before" not in d
        assert "virtual_cash_after" not in d
        assert "alpaca_order_id" not in d

    def test_to_dict_plan_trade_includes_plan_fields(self, db_session):
        """Plan trades should include plan_id and virtual cash in dict."""
        plan = make_plan(db_session)
        trade = make_trade(db_session, plan.id, alpaca_order_id="ord-abc")
        d = trade.to_dict()
        assert d["plan_id"] == plan.id
        assert d["alpaca_order_id"] == "ord-abc"
        assert d["virtual_cash_before"] is not None
        assert d["virtual_cash_after"] is not None

    def test_fractional_quantity(self, db_session):
        """067-fix: quantity is Float, not Integer — supports fractional shares."""
        plan = make_plan(db_session)
        trade = make_trade(db_session, plan.id, quantity=0.2537)
        assert trade.quantity == pytest.approx(0.2537)

    def test_mixed_trades_in_same_table(self, db_session):
        """Both global and plan trades coexist in the same table."""
        plan = make_plan(db_session)
        global_trade = Trade(
            ticker="SPY", action="buy", quantity=5,
            price=Decimal("450.00"), guardrail_passed=True, executed=True,
        )
        db_session.add(global_trade)
        make_trade(db_session, plan.id, ticker="AAPL")

        all_trades = db_session.query(Trade).all()
        assert len(all_trades) == 2

        global_only = db_session.query(Trade).filter(Trade.plan_id.is_(None)).all()
        assert len(global_only) == 1
        assert global_only[0].ticker == "SPY"

        plan_only = db_session.query(Trade).filter(Trade.plan_id == plan.id).all()
        assert len(plan_only) == 1
        assert plan_only[0].ticker == "AAPL"


@pytest.mark.unit
class TestNumericMoneyFields:
    """071-fix: Money fields use Numeric for exact decimal arithmetic."""

    def test_price_stores_exact_decimal(self, db_session):
        """Price should not have float drift."""
        plan = make_plan(db_session)
        trade = make_trade(db_session, plan.id, price=Decimal("149.9999"))
        db_session.refresh(trade)
        # Numeric(14,4) preserves 4 decimal places exactly
        assert trade.price == Decimal("149.9999")

    def test_plan_budget_stores_exact(self, db_session):
        """Plan budget should not drift from float arithmetic."""
        plan = make_plan(db_session, budget=Decimal("10000.50"), virtual_cash=Decimal("10000.50"))
        db_session.refresh(plan)
        assert plan.budget == Decimal("10000.50")
        assert plan.virtual_cash == Decimal("10000.50")

    def test_to_dict_returns_float_not_decimal(self, db_session):
        """API responses should return float, not Decimal (JSON serializable)."""
        plan = make_plan(db_session, budget=Decimal("5000.00"), virtual_cash=Decimal("5000.00"))
        d = plan.to_dict()
        assert isinstance(d["budget"], float)
        assert d["budget"] == 5000.0

    def test_virtual_cash_roundtrip(self, db_session):
        """Virtual cash tracking through Decimal should be exact."""
        plan = make_plan(db_session)
        trade = make_trade(
            db_session, plan.id,
            virtual_cash_before=Decimal("5000.0000"),
            virtual_cash_after=Decimal("4850.2500"),
        )
        d = trade.to_dict()
        assert d["virtual_cash_before"] == 5000.0
        assert d["virtual_cash_after"] == 4850.25
