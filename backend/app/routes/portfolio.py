"""Portfolio API routes."""

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.auth import require_auth
from app.brokers.schwab import SchwabBroker

router = APIRouter()
broker = SchwabBroker()


@router.get("/portfolio")
async def get_portfolio(user: dict = Depends(require_auth)):
    """Current holdings and cash balance."""
    try:
        account_id = "default"
        positions = await broker.get_positions(account_id)
        balance = await broker.get_account_balance(account_id)
        return {"positions": positions, "balance": balance}
    except Exception as e:
        logging.error("Portfolio fetch failed: %s", e)
        raise HTTPException(status_code=503, detail=f"Portfolio unavailable: {e}")
