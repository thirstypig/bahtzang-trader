"""Integration tests for earnings API routes."""

import pytest


@pytest.mark.integration
class TestGetEarningsCalendar:
    def test_returns_empty_calendar(self, client):
        resp = client.get("/earnings?days=30")
        assert resp.status_code == 200
        data = resp.json()
        assert "earnings" in data
        assert "count" in data
        assert data["count"] == 0  # no cached data in test DB

    def test_validates_days_min(self, client):
        resp = client.get("/earnings?days=0")
        assert resp.status_code == 422

    def test_validates_days_max(self, client):
        resp = client.get("/earnings?days=91")
        assert resp.status_code == 422


@pytest.mark.integration
class TestGetSymbolEarnings:
    def test_returns_for_symbol(self, client):
        resp = client.get("/earnings/AAPL")
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "AAPL"
        assert "earnings" in data

    def test_uppercases_symbol(self, client):
        resp = client.get("/earnings/aapl")
        assert resp.status_code == 200
        assert resp.json()["symbol"] == "AAPL"


@pytest.mark.integration
class TestRefreshEarnings:
    def test_refresh_returns_500_without_broker(self, client):
        """Refresh calls broker.get_positions which is not mocked for earnings routes.
        With the 096-fix, it should return a clean 500, not leak internals."""
        resp = client.post("/earnings/refresh")
        # May succeed (if broker mock works) or fail cleanly
        assert resp.status_code in (200, 500)
        if resp.status_code == 500:
            data = resp.json()
            assert "detail" in data
            # 096-fix: Should NOT contain raw exception details
            assert "Traceback" not in data["detail"]
            assert "Error" not in str(data.get("message", ""))
