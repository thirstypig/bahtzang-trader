"""Bot control API routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import require_auth
from app.database import get_db
from app.trade_executor import run_cycle

router = APIRouter()


@router.post("/run")
async def manual_run(
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Manually trigger one trading cycle."""
    result = await run_cycle(db)
    return result
