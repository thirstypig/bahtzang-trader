"""Weekly report API: list, detail, and a manual (rate-limited) re-run."""

from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.auth import require_auth
from app.database import get_db
from app.reports.engine import run_weekly_report
from app.reports.models import WeeklyReport

router = APIRouter(prefix="/reports", tags=["reports"])
_limiter = Limiter(key_func=get_remote_address)


@router.get("")
def list_reports(db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    rows = db.query(WeeklyReport).order_by(WeeklyReport.week_ending.desc()).limit(52).all()
    return [r.to_summary() for r in rows]


@router.get("/{report_id}")
def get_report(report_id: int, db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    r = db.get(WeeklyReport, report_id)
    if r is None:
        raise HTTPException(404, "Report not found")
    return r.to_detail()


@router.post("/run")
@_limiter.limit("2/minute")
async def run_report(request: Request, db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    """Build (or rebuild) the report for the most recent Friday."""
    return (await run_weekly_report(db)).to_detail()
