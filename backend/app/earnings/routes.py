"""Earnings calendar API routes."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import require_auth
from app.brokers.alpaca import AlpacaBroker
from app.database import get_db
from app.earnings.client import get_upcoming_earnings, refresh_earnings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/earnings", tags=["earnings"])

broker = AlpacaBroker()


@router.get("/")
def get_earnings_calendar(
    days: int = Query(30, ge=1, le=90),
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Get upcoming earnings for all cached symbols."""
    events = get_upcoming_earnings(db, days_ahead=days)
    return {"earnings": events, "count": len(events)}


@router.get("/{symbol}")
def get_symbol_earnings(
    symbol: str,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Get upcoming earnings for a specific symbol."""
    events = get_upcoming_earnings(db, symbols=[symbol.upper()], days_ahead=90)
    return {"symbol": symbol.upper(), "earnings": events}


@router.post("/refresh")
async def manual_refresh(
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Manually trigger an earnings data refresh for current holdings."""
    try:
        positions = await broker.get_positions("default")
        symbols = [p.get("instrument", {}).get("symbol", "") for p in positions]
        symbols = [s for s in symbols if s]
        count = await refresh_earnings(db, symbols)
        return {"status": "refreshed", "events_cached": count, "symbols_checked": len(symbols)}
    except Exception as e:
        # 096-fix: Don't leak internal details (DB strings, paths) to client
        logger.error("Earnings refresh failed: %s", e)
        raise HTTPException(status_code=500, detail="Earnings refresh failed. Check server logs.")
