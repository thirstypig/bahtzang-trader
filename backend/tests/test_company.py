"""Tests for the company-profile lookup (Finnhub) + cache + Yahoo link."""

import pytest

from app import company


@pytest.fixture(autouse=True)
def _clear_cache():
    company._cache.clear()
    yield
    company._cache.clear()


# Shape of a Finnhub /stock/profile2 response (subset we use).
FINNHUB_AAPL = {
    "name": "Apple Inc",
    "finnhubIndustry": "Technology",
    "exchange": "NASDAQ NMS - GLOBAL MARKET",
    "marketCapitalization": 3_200_000.0,
    "logo": "https://logo.example/aapl.png",
    "currency": "USD",
    "weburl": "https://www.apple.com/",
}


@pytest.mark.asyncio
async def test_profile_normalizes_finnhub_fields(monkeypatch):
    async def fake_fetch(symbol):
        assert symbol == "AAPL"
        return dict(FINNHUB_AAPL)

    monkeypatch.setattr(company, "_fetch_finnhub_profile", fake_fetch)

    profile = await company.get_company_profile("aapl")  # lower-case in

    assert profile["ticker"] == "AAPL"
    assert profile["name"] == "Apple Inc"
    assert profile["industry"] == "Technology"
    assert profile["exchange"] == "NASDAQ NMS - GLOBAL MARKET"
    assert profile["market_cap"] == 3_200_000.0
    assert profile["logo"] == "https://logo.example/aapl.png"
    assert profile["yahoo_url"] == "https://finance.yahoo.com/quote/AAPL"
    assert profile["source"] == "finnhub"


@pytest.mark.asyncio
async def test_profile_is_cached(monkeypatch):
    calls = {"n": 0}

    async def fake_fetch(symbol):
        calls["n"] += 1
        return dict(FINNHUB_AAPL)

    monkeypatch.setattr(company, "_fetch_finnhub_profile", fake_fetch)

    await company.get_company_profile("AAPL")
    await company.get_company_profile("AAPL")

    assert calls["n"] == 1  # second call served from cache


@pytest.mark.asyncio
async def test_crypto_skips_finnhub_and_uses_dash_yahoo_url(monkeypatch):
    async def boom(symbol):  # must never be called for crypto
        raise AssertionError("Finnhub should not be called for crypto")

    monkeypatch.setattr(company, "_fetch_finnhub_profile", boom)

    profile = await company.get_company_profile("BTC/USD")

    assert profile["ticker"] == "BTC/USD"
    assert profile["industry"] == "Cryptocurrency"
    assert profile["yahoo_url"] == "https://finance.yahoo.com/quote/BTC-USD"
    assert profile["source"] == "none"


@pytest.mark.asyncio
async def test_finnhub_failure_returns_yahoo_only_and_is_not_cached(monkeypatch):
    async def fail(symbol):
        raise RuntimeError("network down")

    monkeypatch.setattr(company, "_fetch_finnhub_profile", fail)

    profile = await company.get_company_profile("AAPL")

    assert profile["name"] is None
    assert profile["yahoo_url"] == "https://finance.yahoo.com/quote/AAPL"
    assert profile["source"] == "none"
    assert "AAPL" not in company._cache  # failures are not cached (retry next time)


def test_company_endpoint_returns_profile(client, monkeypatch):
    async def fake_fetch(symbol):
        return dict(FINNHUB_AAPL)

    monkeypatch.setattr(company, "_fetch_finnhub_profile", fake_fetch)

    res = client.get("/company?symbol=AAPL")

    assert res.status_code == 200
    body = res.json()
    assert body["ticker"] == "AAPL"
    assert body["name"] == "Apple Inc"
    assert body["yahoo_url"] == "https://finance.yahoo.com/quote/AAPL"
