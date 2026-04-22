"""Integration tests for portfolio API routes."""

import pytest
from decimal import Decimal
from app.models import PortfolioSnapshot
from datetime import date


@pytest.mark.integration
class TestGetPortfolioSnapshots:
    def test_empty_snapshots(self, client):
        resp = client.get("/portfolio/snapshots")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_snapshots(self, client, db_engine):
        """Snapshots should be returned as dicts with float values."""
        from sqlalchemy.orm import sessionmaker
        Session = sessionmaker(bind=db_engine)
        db = Session()
        snap = PortfolioSnapshot(
            date=date.today(),
            total_equity=Decimal("50000"),
            cash=Decimal("10000"),
            invested=Decimal("40000"),
            unrealized_pnl=Decimal("500"),
            spy_close=Decimal("450.25"),
        )
        db.add(snap)
        db.commit()
        db.close()

        resp = client.get("/portfolio/snapshots?days=7")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["total_equity"] == 50000.0
        assert data[0]["cash"] == 10000.0
        assert isinstance(data[0]["total_equity"], float)


@pytest.mark.integration
class TestGetPortfolioMetrics:
    def test_insufficient_data(self, client):
        """With 0-1 snapshots, should return error message, not crash."""
        resp = client.get("/portfolio/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["error"] == "insufficient_data"

    def test_metrics_with_data(self, client, db_engine):
        """With 2+ snapshots, should compute metrics."""
        from sqlalchemy.orm import sessionmaker
        from datetime import timedelta
        Session = sessionmaker(bind=db_engine)
        db = Session()
        for i in range(5):
            db.add(PortfolioSnapshot(
                date=date.today() - timedelta(days=5 - i),
                total_equity=Decimal(str(50000 + i * 100)),
                cash=Decimal("10000"),
                invested=Decimal(str(40000 + i * 100)),
                unrealized_pnl=Decimal(str(i * 100)),
            ))
        db.commit()
        db.close()

        resp = client.get("/portfolio/metrics?days=30")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_return_pct" in data
        assert "sharpe_ratio" in data
        assert "max_drawdown_pct" in data


@pytest.mark.integration
class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
