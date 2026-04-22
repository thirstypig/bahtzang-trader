"""Integration tests for bot status and admin routes."""

import pytest
from decimal import Decimal
from app.models import Trade


@pytest.mark.integration
class TestBotStatus:
    def test_returns_status(self, client):
        resp = client.get("/bot/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "running" in data
        assert "frequency" in data
        assert "kill_switch" in data
        assert "total_trades" in data
        assert "schedule_times" in data
        assert data["total_trades"] == 0
        assert data["last_run"] is None

    def test_total_trades_counts_executed(self, client, db_engine):
        from sqlalchemy.orm import sessionmaker
        Session = sessionmaker(bind=db_engine)
        db = Session()

        # Add one executed trade and one non-executed
        db.add(Trade(
            ticker="AAPL", action="buy", quantity=5,
            price=Decimal("150"), guardrail_passed=True, executed=True,
        ))
        db.add(Trade(
            ticker="TSLA", action="buy", quantity=3,
            price=Decimal("200"), guardrail_passed=False, executed=False,
            guardrail_block_reason="Over limit",
        ))
        db.commit()
        db.close()

        resp = client.get("/bot/status")
        assert resp.json()["total_trades"] == 1  # Only executed counts

    def test_last_run_shows_most_recent(self, client, db_engine):
        from sqlalchemy.orm import sessionmaker
        Session = sessionmaker(bind=db_engine)
        db = Session()

        db.add(Trade(
            ticker="SPY", action="hold", quantity=0,
            guardrail_passed=True, executed=False,
        ))
        db.commit()
        db.close()

        resp = client.get("/bot/status")
        data = resp.json()
        assert data["last_run"] is not None
        assert data["last_action"] == "hold"
        assert data["last_ticker"] == "SPY"


@pytest.mark.integration
class TestTradesSummary:
    def test_summary_empty(self, client):
        resp = client.get("/trades/summary")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_summary_excludes_reasoning(self, client, db_engine):
        """Summary endpoint should NOT include claude_reasoning (lightweight)."""
        from sqlalchemy.orm import sessionmaker
        Session = sessionmaker(bind=db_engine)
        db = Session()

        db.add(Trade(
            ticker="AAPL", action="buy", quantity=5,
            price=Decimal("150"), guardrail_passed=True, executed=True,
            claude_reasoning="Long reasoning text that should not appear in summary",
        ))
        db.commit()
        db.close()

        resp = client.get("/trades/summary")
        data = resp.json()
        assert len(data) == 1
        assert "claude_reasoning" not in data[0]
        assert data[0]["ticker"] == "AAPL"


@pytest.mark.integration
class TestFullPlanLifecycle:
    """E2E-style test: create plan → add trades → verify in /trades → export CSV."""

    def test_plan_trades_appear_in_global_trades(self, client, db_engine):
        """067-fix: Plan trades should appear in /trades and /trades/export."""
        # Create a plan
        create_resp = client.post("/plans", json={
            "name": "Lifecycle Test",
            "budget": 5000,
            "trading_goal": "maximize_returns",
        })
        plan_id = create_resp.json()["id"]

        # Insert a plan trade directly (simulating executor)
        from sqlalchemy.orm import sessionmaker
        Session = sessionmaker(bind=db_engine)
        db = Session()
        db.add(Trade(
            ticker="GOOGL", action="buy", quantity=2.5,
            price=Decimal("175.50"), guardrail_passed=True, executed=True,
            plan_id=plan_id,
            virtual_cash_before=Decimal("5000"),
            virtual_cash_after=Decimal("4561.25"),
        ))
        db.commit()
        db.close()

        # Should appear in global /trades
        trades_resp = client.get("/trades")
        tickers = [t["ticker"] for t in trades_resp.json()]
        assert "GOOGL" in tickers

        # Should appear in /trades/export CSV
        export_resp = client.get("/trades/export")
        assert "GOOGL" in export_resp.text
        assert "175.50" in export_resp.text

        # Should also appear in plan detail
        plan_resp = client.get(f"/plans/{plan_id}")
        plan_trades = plan_resp.json()["trades"]
        assert len(plan_trades) == 1
        assert plan_trades[0]["ticker"] == "GOOGL"
