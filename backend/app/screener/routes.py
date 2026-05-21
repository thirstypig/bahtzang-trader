"""Stock screener API routes.

Advisory only — exposes the latest ranked candidates and a manual refresh. Does
not place trades or alter any portfolio's universe.
"""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.auth import require_auth
from app.database import get_db
from app.screener.models import ScreenerCandidate, ScreenerRun

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/screener", tags=["screener"])

_limiter = Limiter(key_func=get_remote_address)


@router.get("")
def get_latest_screen(
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Latest completed screener run with its ranked candidates."""
    run = (
        db.query(ScreenerRun)
        .filter(ScreenerRun.status == "complete")
        .order_by(ScreenerRun.run_at.desc())
        .first()
    )
    # Surface an in-flight run so the UI can show "refreshing…"
    latest_any = db.query(ScreenerRun).order_by(ScreenerRun.run_at.desc()).first()
    if not run:
        return {"run": latest_any.to_dict() if latest_any else None, "candidates": []}

    candidates = (
        db.query(ScreenerCandidate)
        .filter(ScreenerCandidate.run_id == run.id)
        .order_by(ScreenerCandidate.rank)
        .all()
    )
    return {
        "run": run.to_dict(),
        "refreshing": bool(latest_any and latest_any.status == "running"),
        "candidates": [c.to_dict() for c in candidates],
    }


@router.post("/refresh")
@_limiter.limit("2/minute")
async def refresh_screen(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Kick off a screener run in the background (it scans ~500 names)."""
    background_tasks.add_task(_run_screener_bg)
    return {"status": "started"}


def _run_screener_bg():
    """Background task — owns its DB session (the request's is closed by now)."""
    import asyncio

    from app.database import SessionLocal
    from app.screener.engine import run_screener

    db = SessionLocal()
    try:
        asyncio.run(run_screener(db))
    except Exception as e:
        logger.exception("Background screener run failed: %s", e)
    finally:
        db.close()
