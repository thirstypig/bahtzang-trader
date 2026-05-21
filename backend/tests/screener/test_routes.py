"""Screener API route tests (integration via TestClient)."""

import pytest

# Register models with Base.metadata before the test DB is built.
from app.models import ScreenerRun, ScreenerCandidate  # noqa: F401


@pytest.mark.integration
class TestScreenerRoutes:
    def test_empty_returns_no_run(self, client):
        resp = client.get("/screener")
        assert resp.status_code == 200
        body = resp.json()
        assert body["run"] is None
        assert body["candidates"] == []

    def test_latest_returns_complete_run_with_candidates(self, client, db_session):
        run = ScreenerRun(universe_size=3, scored_count=2, status="complete")
        db_session.add(run)
        db_session.commit()
        db_session.refresh(run)
        db_session.add_all([
            ScreenerCandidate(run_id=run.id, rank=1, ticker="NVDA", composite_score=1.8,
                              momentum=0.4, rel_strength=0.2, trend_score=1.0, rsi=62, volatility=0.3, price=900),
            ScreenerCandidate(run_id=run.id, rank=2, ticker="AAPL", composite_score=1.1,
                              momentum=0.2, rel_strength=0.1, trend_score=1.0, rsi=55, volatility=0.25, price=210),
        ])
        db_session.commit()

        body = client.get("/screener").json()
        assert body["run"]["status"] == "complete"
        assert [c["ticker"] for c in body["candidates"]] == ["NVDA", "AAPL"]
        assert body["candidates"][0]["rank"] == 1

    def test_refresh_starts_background_run(self, client, monkeypatch):
        # Stub the heavy background task so the test doesn't hit the network.
        ran = {}
        import app.screener.routes as routes
        monkeypatch.setattr(routes, "_run_screener_bg", lambda: ran.setdefault("called", True))

        resp = client.post("/screener/refresh")
        assert resp.status_code == 200
        assert resp.json()["status"] == "started"
        assert ran.get("called") is True
