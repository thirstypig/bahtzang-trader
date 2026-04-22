"""Integration tests for guardrails + kill switch API routes.

These endpoints control real-money risk limits — the highest-value
tests in the suite. A regression here could allow uncontrolled trading.
"""

import pytest
from unittest.mock import patch, AsyncMock


@pytest.mark.integration
class TestGetGuardrails:
    def test_returns_default_config(self, client):
        resp = client.get("/guardrails")
        assert resp.status_code == 200
        data = resp.json()
        assert "risk_profile" in data
        assert "kill_switch" in data
        assert "max_total_invested" in data
        assert data["kill_switch"] is False

    def test_returns_trading_goal(self, client):
        resp = client.get("/guardrails")
        data = resp.json()
        assert data["trading_goal"] in [
            "maximize_returns", "steady_income", "capital_preservation",
            "beat_sp500", "swing_trading", "passive_index",
        ]


@pytest.mark.integration
class TestGetPresets:
    def test_returns_presets_and_goals(self, client):
        resp = client.get("/guardrails/presets")
        assert resp.status_code == 200
        data = resp.json()
        assert "risk_presets" in data
        assert "trading_goals" in data
        assert "conservative" in data["risk_presets"]
        assert "moderate" in data["risk_presets"]
        assert "aggressive" in data["risk_presets"]


@pytest.mark.integration
class TestUpdateGuardrails:
    def test_update_risk_profile(self, client):
        with patch("app.routes.guardrails.apply_schedule"):
            resp = client.post("/guardrails", json={
                "risk_profile": "aggressive",
            })
        assert resp.status_code == 200
        data = resp.json()
        assert data["risk_profile"] == "aggressive"

    def test_update_trading_goal(self, client):
        with patch("app.routes.guardrails.apply_schedule"):
            resp = client.post("/guardrails", json={
                "trading_goal": "steady_income",
            })
        assert resp.status_code == 200
        assert resp.json()["trading_goal"] == "steady_income"

    def test_update_creates_audit_entry(self, client):
        with patch("app.routes.guardrails.apply_schedule"):
            client.post("/guardrails", json={"risk_profile": "conservative"})
        # Verify by checking bot status which includes recent_changes
        resp = client.get("/bot/status")
        data = resp.json()
        assert len(data["recent_changes"]) > 0

    def test_rejects_invalid_goal(self, client):
        resp = client.post("/guardrails", json={
            "trading_goal": "yolo_moon",
        })
        assert resp.status_code == 422


@pytest.mark.integration
class TestKillSwitch:
    """Kill switch is the most critical safety control — test thoroughly."""

    def test_activate_kill_switch(self, client):
        with patch("app.routes.guardrails.notifier") as mock_notifier:
            mock_notifier.notify_kill_switch = AsyncMock()
            resp = client.post("/killswitch")
        assert resp.status_code == 200
        assert resp.json()["kill_switch"] is True

        # Verify it's actually persisted
        config = client.get("/guardrails").json()
        assert config["kill_switch"] is True

    def test_deactivate_kill_switch(self, client):
        with patch("app.routes.guardrails.notifier") as mock_notifier:
            mock_notifier.notify_kill_switch = AsyncMock()
            # Activate first
            client.post("/killswitch")
            # Then deactivate
            resp = client.post("/killswitch/deactivate")
        assert resp.status_code == 200
        assert resp.json()["kill_switch"] is False

        config = client.get("/guardrails").json()
        assert config["kill_switch"] is False

    def test_kill_switch_cycle_creates_audit_entries(self, client):
        """Both activate and deactivate should be audited."""
        with patch("app.routes.guardrails.notifier") as mock_notifier:
            mock_notifier.notify_kill_switch = AsyncMock()
            client.post("/killswitch")
            client.post("/killswitch/deactivate")

        resp = client.get("/bot/status")
        changes = resp.json()["recent_changes"]
        actions = [c["action"] for c in changes]
        assert "kill_switch_activated" in actions
        assert "kill_switch_deactivated" in actions
