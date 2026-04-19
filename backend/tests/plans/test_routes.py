"""Integration tests for plan API routes via TestClient.

Budget validation (pg_advisory_xact_lock) is stubbed in conftest since
SQLite doesn't support PostgreSQL advisory locks.
"""

import pytest


@pytest.mark.integration
class TestListPlans:
    def test_list_empty(self, client):
        resp = client.get("/plans")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_returns_plans(self, client):
        client.post("/plans", json={
            "name": "Growth",
            "budget": 1000,
            "trading_goal": "maximize_returns",
        })
        resp = client.get("/plans")
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "Growth"
        assert data[0]["trade_count"] == 0


@pytest.mark.integration
class TestCreatePlan:
    def test_create_basic(self, client):
        resp = client.post("/plans", json={
            "name": "Income",
            "budget": 5000,
            "trading_goal": "steady_income",
            "risk_profile": "conservative",
            "trading_frequency": "1x",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Income"
        assert data["budget"] == 5000.0
        assert data["virtual_cash"] == 5000.0
        assert data["is_active"] is True

    def test_create_with_target(self, client):
        resp = client.post("/plans", json={
            "name": "Growth",
            "budget": 5000,
            "trading_goal": "maximize_returns",
            "target_amount": 10000,
            "target_date": "2027-06-01",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["target_amount"] == 10000
        assert data["target_date"] == "2027-06-01"

    def test_create_validates_goal(self, client):
        resp = client.post("/plans", json={
            "name": "Bad",
            "budget": 1000,
            "trading_goal": "yolo",
        })
        assert resp.status_code == 422

    def test_create_validates_budget_positive(self, client):
        resp = client.post("/plans", json={
            "name": "Bad",
            "budget": -100,
            "trading_goal": "maximize_returns",
        })
        assert resp.status_code == 422

    def test_create_validates_name_length(self, client):
        resp = client.post("/plans", json={
            "name": "x" * 101,
            "budget": 1000,
            "trading_goal": "maximize_returns",
        })
        assert resp.status_code == 422


@pytest.mark.integration
class TestGetPlan:
    def test_get_existing(self, client):
        create_resp = client.post("/plans", json={
            "name": "Test",
            "budget": 1000,
            "trading_goal": "maximize_returns",
        })
        plan_id = create_resp.json()["id"]
        resp = client.get(f"/plans/{plan_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Test"
        assert "trades" in resp.json()

    def test_get_nonexistent(self, client):
        resp = client.get("/plans/99999")
        assert resp.status_code == 404


@pytest.mark.integration
class TestUpdatePlan:
    def _create_plan(self, client):
        resp = client.post("/plans", json={
            "name": "Test",
            "budget": 5000,
            "trading_goal": "maximize_returns",
        })
        return resp.json()["id"]

    def test_update_name(self, client):
        plan_id = self._create_plan(client)
        resp = client.patch(f"/plans/{plan_id}", json={"name": "Renamed"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "Renamed"

    def test_pause_plan(self, client):
        plan_id = self._create_plan(client)
        resp = client.patch(f"/plans/{plan_id}", json={"is_active": False})
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    def test_clear_target_date(self, client):
        """097-fix: exclude_unset allows sending null to clear fields."""
        plan_id = self._create_plan(client)
        # Set a target
        client.patch(f"/plans/{plan_id}", json={
            "target_amount": 10000, "target_date": "2027-01-01",
        })
        # Clear it
        resp = client.patch(f"/plans/{plan_id}", json={
            "target_amount": None, "target_date": None,
        })
        assert resp.status_code == 200
        assert resp.json()["target_amount"] is None
        assert resp.json()["target_date"] is None

    def test_update_nonexistent(self, client):
        resp = client.patch("/plans/99999", json={"name": "Nope"})
        assert resp.status_code == 404


@pytest.mark.integration
class TestDeletePlan:
    def _create_plan(self, client):
        resp = client.post("/plans", json={
            "name": "Deletable",
            "budget": 1000,
            "trading_goal": "maximize_returns",
        })
        return resp.json()["id"]

    def test_delete_empty_plan(self, client):
        plan_id = self._create_plan(client)
        resp = client.delete(f"/plans/{plan_id}")
        assert resp.status_code == 200
        assert client.get(f"/plans/{plan_id}").status_code == 404

    def test_delete_nonexistent(self, client):
        resp = client.delete("/plans/99999")
        assert resp.status_code == 404


@pytest.mark.integration
class TestExportCsv:
    def test_export_empty(self, client):
        create_resp = client.post("/plans", json={
            "name": "Export Test",
            "budget": 1000,
            "trading_goal": "maximize_returns",
        })
        plan_id = create_resp.json()["id"]
        resp = client.get(f"/plans/{plan_id}/export")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        assert "Date,Action,Ticker" in resp.text

    def test_export_nonexistent(self, client):
        resp = client.get("/plans/99999/export")
        assert resp.status_code == 404


@pytest.mark.integration
class TestSnapshots:
    def test_snapshots_empty(self, client):
        create_resp = client.post("/plans", json={
            "name": "Snap Test",
            "budget": 1000,
            "trading_goal": "maximize_returns",
        })
        plan_id = create_resp.json()["id"]
        resp = client.get(f"/plans/{plan_id}/snapshots")
        assert resp.status_code == 200
        assert resp.json() == []
