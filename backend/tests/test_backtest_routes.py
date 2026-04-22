"""Integration tests for /backtest routes.

Covers the HTTP contract for backtest CRUD + strategy listing.
The backtest engine (which fetches OHLCV from Alpaca) is mocked to
avoid external network calls.
"""

import pytest
from unittest.mock import patch, AsyncMock


@pytest.mark.integration
class TestListStrategies:
    def test_returns_list_of_strategies(self, client):
        resp = client.get("/backtest/strategies")
        assert resp.status_code == 200
        strategies = resp.json()
        assert isinstance(strategies, list)
        assert len(strategies) >= 3  # sma_crossover, rsi_mean_reversion, buy_and_hold

    def test_each_strategy_has_required_fields(self, client):
        resp = client.get("/backtest/strategies")
        for s in resp.json():
            assert "id" in s
            assert "name" in s
            assert "description" in s
            assert "params" in s
            assert isinstance(s["params"], list)

    def test_known_strategies_present(self, client):
        resp = client.get("/backtest/strategies")
        ids = {s["id"] for s in resp.json()}
        assert "sma_crossover" in ids
        assert "rsi_mean_reversion" in ids
        assert "buy_and_hold" in ids


@pytest.mark.integration
class TestListBacktests:
    def test_returns_empty_list_initially(self, client):
        resp = client.get("/backtest/")
        assert resp.status_code == 200
        assert resp.json() == []


@pytest.mark.integration
class TestGetBacktestResult:
    def test_404_for_nonexistent_result(self, client):
        resp = client.get("/backtest/99999")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


@pytest.mark.integration
class TestDeleteBacktest:
    def test_404_for_nonexistent_config(self, client):
        resp = client.delete("/backtest/99999")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


@pytest.mark.integration
class TestCreateAndRunBacktest:
    """POST /backtest — mocks the background engine to avoid Alpaca calls."""

    VALID_BODY = {
        "name": "Test SMA Backtest",
        "strategy": "sma_crossover",
        "tickers": ["AAPL", "MSFT"],
        "start_date": "2024-01-01",
        "end_date": "2024-06-01",
        "initial_capital": 100000,
        "params": {"fast_period": 20, "slow_period": 50},
    }

    def test_create_returns_pending(self, client):
        """POST creates config + result rows and returns pending status."""
        with patch(
            "app.backtest.routes._run_backtest_bg"
        ) as mock_bg:
            resp = client.post("/backtest/", json=self.VALID_BODY)

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "pending"
        assert "config_id" in data
        assert "result_id" in data

    def test_created_backtest_appears_in_list(self, client):
        """After POST, GET /backtest/ includes the new entry."""
        with patch("app.backtest.routes._run_backtest_bg"):
            client.post("/backtest/", json=self.VALID_BODY)

        resp = client.get("/backtest/")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["name"] == "Test SMA Backtest"
        assert items[0]["strategy"] == "sma_crossover"
        assert items[0]["tickers"] == ["AAPL", "MSFT"]

    def test_get_result_by_id(self, client):
        """GET /backtest/{result_id} returns full detail for a created backtest."""
        with patch("app.backtest.routes._run_backtest_bg"):
            post_resp = client.post("/backtest/", json=self.VALID_BODY)

        result_id = post_resp.json()["result_id"]
        resp = client.get(f"/backtest/{result_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "pending"
        assert data["config"]["name"] == "Test SMA Backtest"
        assert "equity_curve" in data
        assert "trades_log" in data

    def test_delete_created_backtest(self, client):
        """DELETE /backtest/{config_id} removes config and results."""
        with patch("app.backtest.routes._run_backtest_bg"):
            post_resp = client.post("/backtest/", json=self.VALID_BODY)

        config_id = post_resp.json()["config_id"]
        del_resp = client.delete(f"/backtest/{config_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["status"] == "deleted"

        # Verify it's gone from the list
        list_resp = client.get("/backtest/")
        assert list_resp.json() == []

    def test_unknown_strategy_returns_400(self, client):
        body = {**self.VALID_BODY, "strategy": "nonexistent_strategy"}
        resp = client.post("/backtest/", json=body)
        assert resp.status_code == 400
        assert "Unknown strategy" in resp.json()["detail"]

    def test_end_date_before_start_date_returns_400(self, client):
        body = {
            **self.VALID_BODY,
            "start_date": "2024-06-01",
            "end_date": "2024-01-01",
        }
        resp = client.post("/backtest/", json=body)
        assert resp.status_code == 400
        assert "end_date" in resp.json()["detail"].lower()

    def test_tickers_uppercased(self, client):
        """Tickers should be stored uppercase regardless of input."""
        body = {**self.VALID_BODY, "tickers": ["aapl", "msft"]}
        with patch("app.backtest.routes._run_backtest_bg"):
            client.post("/backtest/", json=body)

        resp = client.get("/backtest/")
        assert resp.json()[0]["tickers"] == ["AAPL", "MSFT"]
