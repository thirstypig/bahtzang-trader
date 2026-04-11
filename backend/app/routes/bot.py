"""Bot control API routes."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import require_auth
from app.database import get_db
from app.trade_executor import run_cycle

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/run")
async def manual_run(
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Manually trigger one trading cycle."""
    try:
        result = await run_cycle(db)
        return result
    except Exception as e:
        logger.error("Trading cycle failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Trading cycle failed: {e}")
