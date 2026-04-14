"""Schwab brokerage API client with token caching and shared HTTP client."""

import logging
import time

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

TOKEN_URL = "https://api.schwabapi.com/v1/oauth/token"
BASE_URL = "https://api.schwabapi.com/trader/v1"

# 003-fix: Token cache with expiry tracking
_token_cache: dict = {}

# 007-fix: Shared HTTP client for connection pooling
_http_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    """Return a shared httpx client for connection pooling."""
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(base_url=BASE_URL, timeout=15.0)
    return _http_client


async def _get_access_token() -> str:
    """Authenticate via Schwab OAuth client credentials and cache the token."""
    # 003-fix: Check expiry before returning cached token
    if (
        _token_cache.get("access_token")
        and _token_cache.get("expires_at", 0) > time.time()
    ):
        return _token_cache["access_token"]

    # 007-fix: Reuse shared client (absolute URL overrides base_url)
    client = _get_client()
    resp = await client.post(
        TOKEN_URL,
        data={"grant_type": "client_credentials"},
        auth=(settings.SCHWAB_CLIENT_ID, settings.SCHWAB_CLIENT_SECRET),
    )
    resp.raise_for_status()
    data = resp.json()
    _token_cache["access_token"] = data["access_token"]
    # 003-fix: Store expiry with 60s buffer
    _token_cache["expires_at"] = time.time() + data.get("expires_in", 1800) - 60
    return data["access_token"]


async def _headers() -> dict:
    token = await _get_access_token()
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}


async def get_positions(account_id: str) -> list[dict]:
    """Fetch current portfolio positions for a given account."""
    client = _get_client()
    resp = await client.get(
        f"/accounts/{account_id}/positions",
        headers=await _headers(),
    )
    resp.raise_for_status()
    return resp.json().get("securitiesAccount", {}).get("positions", [])


async def get_account_balance(account_id: str) -> dict:
    """Fetch account balances including cash available."""
    client = _get_client()
    resp = await client.get(
        f"/accounts/{account_id}",
        headers=await _headers(),
    )
    resp.raise_for_status()
    balances = (
        resp.json()
        .get("securitiesAccount", {})
        .get("currentBalances", {})
    )
    return {
        "cash_available": balances.get("cashBalance", 0),
        "total_value": balances.get("liquidationValue", 0),
    }


async def place_order(
    account_id: str, ticker: str, action: str, quantity: int
) -> dict:
    """Place a buy or sell market order on Schwab."""
    if action not in ("buy", "sell"):
        raise ValueError(f"Invalid action: {action}. Must be 'buy' or 'sell'.")

    order_payload = {
        "orderType": "MARKET",
        "session": "NORMAL",
        "duration": "DAY",
        "orderStrategyType": "SINGLE",
        "orderLegCollection": [
            {
                "instruction": "BUY" if action == "buy" else "SELL",
                "quantity": quantity,
                "instrument": {"symbol": ticker, "assetType": "EQUITY"},
            }
        ],
    }

    client = _get_client()
    resp = await client.post(
        f"/accounts/{account_id}/orders",
        headers=await _headers(),
        json=order_payload,
    )
    resp.raise_for_status()
    return {"status": "filled", "status_code": resp.status_code}
