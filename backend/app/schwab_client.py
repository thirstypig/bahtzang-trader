import httpx

from app.config import settings

AUTH_URL = "https://api.schwabapi.com/v1/oauth/authorize"
TOKEN_URL = "https://api.schwabapi.com/v1/oauth/token"
BASE_URL = "https://api.schwabapi.com/trader/v1"

_token_cache: dict = {}


async def _get_access_token() -> str:
    """Authenticate via Schwab OAuth client credentials and cache the token."""
    if _token_cache.get("access_token"):
        return _token_cache["access_token"]

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            TOKEN_URL,
            data={"grant_type": "client_credentials"},
            auth=(settings.SCHWAB_CLIENT_ID, settings.SCHWAB_CLIENT_SECRET),
        )
        resp.raise_for_status()
        data = resp.json()
        _token_cache["access_token"] = data["access_token"]
        return data["access_token"]


async def _headers() -> dict:
    token = await _get_access_token()
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}


async def get_positions(account_id: str) -> list[dict]:
    """Fetch current portfolio positions for a given account."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{BASE_URL}/accounts/{account_id}/positions",
            headers=await _headers(),
        )
        resp.raise_for_status()
        return resp.json().get("securitiesAccount", {}).get("positions", [])


async def get_account_balance(account_id: str) -> dict:
    """Fetch account balances including cash available."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{BASE_URL}/accounts/{account_id}",
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

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{BASE_URL}/accounts/{account_id}/orders",
            headers=await _headers(),
            json=order_payload,
        )
        resp.raise_for_status()
        return {"status": "filled", "status_code": resp.status_code}


def clear_token_cache():
    """Clear cached OAuth token (useful after expiry)."""
    _token_cache.clear()
