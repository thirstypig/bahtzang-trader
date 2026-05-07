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


@pytest.mark.integration
class TestBlockStats:
    """GET /trades/block-stats — verifies the audit-log noise cleanup
    after the zero-qty + headroom fixes."""

    def test_empty_window_returns_zero_blocks(self, client):
        resp = client.get("/trades/block-stats?days=14")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_blocked"] == 0
        assert body["block_rate_pct"] == 0
        assert body["by_reason"] == []

    def test_aggregates_blocks_by_reason(self, client, db_engine):
        from datetime import datetime, timezone
        from sqlalchemy.orm import sessionmaker
        Session = sessionmaker(bind=db_engine)
        db = Session()

        # 3 blocks with same reason, 1 with different reason, 1 executed
        for _ in range(3):
            db.add(Trade(
                ticker="AAPL", action="buy", quantity=1, price=Decimal("100"),
                guardrail_passed=False, executed=False,
                guardrail_block_reason="Insufficient plan cash: $0.21 < $99.99",
                timestamp=datetime.now(timezone.utc),
            ))
        db.add(Trade(
            ticker="MSFT", action="buy", quantity=1, price=Decimal("100"),
            guardrail_passed=False, executed=False,
            guardrail_block_reason="Confidence below minimum",
            timestamp=datetime.now(timezone.utc),
        ))
        db.add(Trade(
            ticker="NVDA", action="buy", quantity=1, price=Decimal("100"),
            guardrail_passed=True, executed=True,
            timestamp=datetime.now(timezone.utc),
        ))
        db.commit()

        resp = client.get("/trades/block-stats?days=14")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_decisions"] == 5
        assert body["total_executed"] == 1
        assert body["total_blocked"] == 4
        # Top reason is the cash one (3 blocks)
        assert body["by_reason"][0]["reason"] == "Insufficient plan cash: $0.21 < $99.99"
        assert body["by_reason"][0]["count"] == 3
        assert body["by_reason"][1]["count"] == 1
        db.close()

    def test_window_excludes_old_blocks(self, client, db_engine):
        from datetime import datetime, timedelta, timezone
        from sqlalchemy.orm import sessionmaker
        Session = sessionmaker(bind=db_engine)
        db = Session()

        # Block from 30 days ago — should be excluded by days=14 window
        db.add(Trade(
            ticker="OLD", action="buy", quantity=1, price=Decimal("100"),
            guardrail_passed=False, executed=False,
            guardrail_block_reason="Old block",
            timestamp=datetime.now(timezone.utc) - timedelta(days=30),
        ))
        # Recent block — should be counted
        db.add(Trade(
            ticker="NEW", action="buy", quantity=1, price=Decimal("100"),
            guardrail_passed=False, executed=False,
            guardrail_block_reason="Recent block",
            timestamp=datetime.now(timezone.utc),
        ))
        db.commit()

        resp = client.get("/trades/block-stats?days=14")
        body = resp.json()
        assert body["total_blocked"] == 1
        assert body["by_reason"][0]["reason"] == "Recent block"
        db.close()
