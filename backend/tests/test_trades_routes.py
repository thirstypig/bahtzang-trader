"""Integration tests for /trades routes with the unified Trade model.

067-fix: Verifies that global trades and plan trades coexist correctly,
and that /trades/export includes plan trades (the original bug).
"""

import pytest
from decimal import Decimal
from app.models import Trade


@pytest.mark.integration
class TestTradesEndpoint:
    def test_get_trades_empty(self, client):
        resp = client.get("/trades")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_trades_includes_plan_trades(self, client, db_engine):
        """067-fix: /trades should return both global and plan trades."""
        from sqlalchemy.orm import sessionmaker
        from tests.conftest import make_plan
        Session = sessionmaker(bind=db_engine)
        db = Session()

        # Create a plan trade
        plan = make_plan(db)
        plan_trade = Trade(
            ticker="AAPL", action="buy", quantity=1.0,
            price=Decimal("150.00"), guardrail_passed=True, executed=True,
            plan_id=plan.id, virtual_cash_before=Decimal("5000"),
            virtual_cash_after=Decimal("4850"),
        )
        db.add(plan_trade)

        # Create a global trade
        global_trade = Trade(
            ticker="SPY", action="buy", quantity=5,
            price=Decimal("450.00"), guardrail_passed=True, executed=True,
        )
        db.add(global_trade)
        db.commit()

        resp = client.get("/trades?limit=50")
        assert resp.status_code == 200
        trades = resp.json()
        assert len(trades) == 2
        tickers = {t["ticker"] for t in trades}
        assert tickers == {"AAPL", "SPY"}
        db.close()


@pytest.mark.integration
class TestTradesExport:
    def test_export_includes_plan_trades(self, client, db_engine):
        """067-fix: /trades/export must include plan trades for tax reporting."""
        from sqlalchemy.orm import sessionmaker
        from tests.conftest import make_plan
        Session = sessionmaker(bind=db_engine)
        db = Session()

        plan = make_plan(db)
        trade = Trade(
            ticker="NVDA", action="buy", quantity=2.5,
            price=Decimal("800.00"), guardrail_passed=True, executed=True,
            plan_id=plan.id, virtual_cash_before=Decimal("5000"),
            virtual_cash_after=Decimal("3000"),
        )
        db.add(trade)
        db.commit()

        resp = client.get("/trades/export")
        assert resp.status_code == 200
        assert "NVDA" in resp.text
        assert "800.00" in resp.text
        db.close()
