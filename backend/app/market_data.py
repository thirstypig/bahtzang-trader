"""Alpha Vantage market data: live quotes and news sentiment."""

import asyncio

import httpx

from app.config import settings

BASE_URL = "https://www.alphavantage.co/query"

# 007-fix: Shared HTTP client for connection pooling
_http_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=15.0)
    return _http_client


async def get_quote(ticker: str) -> dict:
    """Fetch a real-time quote for a single ticker from Alpha Vantage."""
    params = {
        "function": "GLOBAL_QUOTE",
        "symbol": ticker,
        "apikey": settings.ALPHA_VANTAGE_KEY,
    }
    client = _get_client()
    resp = await client.get(BASE_URL, params=params)
    resp.raise_for_status()
    raw = resp.json().get("Global Quote", {})

    return {
        "ticker": raw.get("01. symbol", ticker),
        "price": float(raw.get("05. price", 0)),
        "change_pct": raw.get("10. change percent", "0%"),
        "volume": int(raw.get("06. volume", 0)),
    }


async def get_quotes(tickers: list[str]) -> list[dict]:
    """Fetch quotes for multiple tickers in parallel."""
    # 006-fix: Use asyncio.gather instead of sequential loop
    return list(await asyncio.gather(*(get_quote(t) for t in tickers)))


async def get_news(tickers: list[str] | None = None) -> list[dict]:
    """Fetch latest news headlines from Alpha Vantage News Sentiment API."""
    params = {
        "function": "NEWS_SENTIMENT",
        "apikey": settings.ALPHA_VANTAGE_KEY,
        "limit": "10",
    }
    if tickers:
        params["tickers"] = ",".join(tickers)

    client = _get_client()
    resp = await client.get(BASE_URL, params=params)
    resp.raise_for_status()
    feed = resp.json().get("feed", [])

    return [
        {
            "title": item.get("title", ""),
            "summary": item.get("summary", ""),
            "source": item.get("source", ""),
            "sentiment": item.get("overall_sentiment_label", ""),
            "sentiment_score": item.get("overall_sentiment_score", 0),
        }
        for item in feed[:10]
    ]
