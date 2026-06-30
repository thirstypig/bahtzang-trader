"""Company-profile lookup for the ticker hover card.

Profiles (name, industry, exchange, market cap, logo) are effectively static,
so we cache them per-ticker for the process lifetime — each symbol hits Finnhub
at most once per deploy, which keeps us well under the free-tier rate limit.

Crypto slash-pairs ("BTC/USD") skip Finnhub (it has no equity profile for them)
and just carry a Yahoo link with the dash form Yahoo expects ("BTC-USD").
The Finnhub key is a backend secret, so the browser reaches this via the
authenticated GET /company?symbol= route rather than calling Finnhub directly.
"""

import logging

import httpx
from fastapi import APIRouter, Depends, Query

from app.auth import require_auth
from app.config import settings
from app.symbols import is_crypto

logger = logging.getLogger(__name__)

FINNHUB_BASE = "https://finnhub.io/api/v1"

# Process-lifetime cache: ticker -> normalized profile dict.
_cache: dict[str, dict] = {}
_http_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=10.0)
    return _http_client


def _yahoo_url(symbol: str) -> str:
    """Yahoo Finance quote URL. Crypto pairs use a dash: BTC/USD -> BTC-USD."""
    return f"https://finance.yahoo.com/quote/{symbol.replace('/', '-')}"


def _empty_profile(symbol: str) -> dict:
    """A profile with no company metadata — just the symbol + Yahoo link."""
    return {
        "ticker": symbol,
        "name": None,
        "industry": None,
        "exchange": None,
        "market_cap": None,
        "logo": None,
        "currency": None,
        "website": None,
        "yahoo_url": _yahoo_url(symbol),
        "source": "none",
    }


async def _fetch_finnhub_profile(symbol: str) -> dict:
    """Raw Finnhub /stock/profile2 call. Raises on transport/HTTP error."""
    resp = await _get_client().get(
        f"{FINNHUB_BASE}/stock/profile2",
        params={"symbol": symbol, "token": settings.FINNHUB_API_KEY},
    )
    resp.raise_for_status()
    return resp.json() or {}


async def get_company_profile(ticker: str) -> dict:
    """Return a normalized company profile for ``ticker`` (cached).

    Always returns a dict with a usable ``yahoo_url`` even when no company
    metadata is available (crypto, missing key, or a Finnhub failure).
    """
    symbol = (ticker or "").upper().strip()
    if not symbol:
        return _empty_profile("")

    if symbol in _cache:
        return _cache[symbol]

    # Crypto pairs have no Finnhub equity profile — Yahoo link only.
    if is_crypto(symbol):
        profile = _empty_profile(symbol)
        profile["industry"] = "Cryptocurrency"
        _cache[symbol] = profile
        return profile

    if not settings.FINNHUB_API_KEY:
        return _empty_profile(symbol)  # not cached — key may arrive via env

    try:
        data = await _fetch_finnhub_profile(symbol)
    except Exception as e:
        # Don't cache failures so a transient outage retries next hover.
        logger.warning("Finnhub profile fetch failed for %s: %s", symbol, e)
        return _empty_profile(symbol)

    profile = {
        "ticker": symbol,
        "name": data.get("name") or None,
        "industry": data.get("finnhubIndustry") or None,
        "exchange": data.get("exchange") or None,
        "market_cap": data.get("marketCapitalization"),  # millions USD
        "logo": data.get("logo") or None,
        "currency": data.get("currency") or None,
        "website": data.get("weburl") or None,
        "yahoo_url": _yahoo_url(symbol),
        "source": "finnhub",
    }
    _cache[symbol] = profile
    return profile


router = APIRouter(prefix="/company", tags=["company"])


@router.get("")
async def company_profile(
    symbol: str = Query(..., min_length=1, max_length=15),
    user: dict = Depends(require_auth),
):
    """Company profile + Yahoo link for a ticker (e.g. ?symbol=AAPL)."""
    return await get_company_profile(symbol)
