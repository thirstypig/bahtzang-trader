"""Route-level: validation + persistence (background runner not exercised)."""

from datetime import date


def test_list_supported_symbols(client):
    r = client.get("/forex/symbols")
    assert r.status_code == 200
    body = r.json()
    assert "EURUSD" in body
    assert "USDJPY" in body


def test_create_backtest_rejects_bad_dates(client):
    r = client.post("/forex/backtests", json={
        "name": "test",
        "symbols": ["EURUSD"],
        "start_date": "2024-06-01",
        "end_date": "2024-01-01",
    })
    assert r.status_code == 400


def test_create_backtest_rejects_unknown_symbol(client):
    r = client.post("/forex/backtests", json={
        "name": "test",
        "symbols": ["XYZUSD"],
        "start_date": "2024-01-01",
        "end_date": "2024-06-01",
    })
    assert r.status_code == 400


def test_create_and_list_backtest(client, monkeypatch):
    # Stub the background runner so we don't hit yfinance during this test
    import app.forex.routes as routes_mod
    monkeypatch.setattr(routes_mod, "_run_backtest_bg", lambda run_id: None)

    r = client.post("/forex/backtests", json={
        "name": "smoke",
        "symbols": ["EURUSD"],
        "start_date": "2024-01-01",
        "end_date": "2024-06-01",
    })
    assert r.status_code == 200, r.text
    run_id = r.json()["run_id"]

    listing = client.get("/forex/backtests")
    assert listing.status_code == 200
    items = listing.json()
    assert any(it["id"] == run_id for it in items)

    detail = client.get(f"/forex/backtests/{run_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["id"] == run_id
    assert body["symbols"] == ["EURUSD"]
    assert body["risk_pct"] == 0.02


def test_get_nonexistent_backtest_returns_404(client):
    r = client.get("/forex/backtests/99999")
    assert r.status_code == 404


def test_delete_backtest(client, monkeypatch):
    import app.forex.routes as routes_mod
    monkeypatch.setattr(routes_mod, "_run_backtest_bg", lambda run_id: None)

    r = client.post("/forex/backtests", json={
        "name": "to-delete",
        "symbols": ["GBPUSD"],
        "start_date": "2024-01-01",
        "end_date": "2024-06-01",
    })
    run_id = r.json()["run_id"]

    d = client.delete(f"/forex/backtests/{run_id}")
    assert d.status_code == 200
    assert d.json()["status"] == "deleted"

    g = client.get(f"/forex/backtests/{run_id}")
    assert g.status_code == 404
