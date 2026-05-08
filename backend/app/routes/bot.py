"""Bot control API routes."""

import logging
import traceback
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.auth import require_auth
from app.database import get_db
from app.error_tracker import record_error, get_recent_errors, get_error_by_ref, get_error_count
from app.models import Trade
from app.plans.executor import run_all_plans
from app.plans.models import Portfolio
from app.scheduler import scheduler, FREQUENCY_SCHEDULES, _max_frequency_among_active

router = APIRouter()
logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)

# Map exception types to user-friendly error codes
ERROR_CODES = {
    "ModuleNotFoundError": "MISSING_DEPENDENCY",
    "ImportError": "MISSING_DEPENDENCY",
    "ConnectionError": "BROKER_UNREACHABLE",
    "TimeoutError": "BROKER_TIMEOUT",
    "APITimeoutError": "CLAUDE_TIMEOUT",
    "AuthenticationError": "AUTH_FAILED",
    "APIError": "CLAUDE_API_ERROR",
    "JSONDecodeError": "INVALID_RESPONSE",
    "KeyError": "DATA_ERROR",
    "TypeError": "DATA_ERROR",
    "ValueError": "DATA_ERROR",
}


def _classify_error(e: Exception) -> dict:
    """Classify an exception into a user-friendly error code + message.

    Returns safe diagnostic info without leaking secrets or internal paths.
    """
    exc_type = type(e).__name__
    code = ERROR_CODES.get(exc_type, "INTERNAL_ERROR")

    # Build a safe, helpful message based on the error type
    if code == "MISSING_DEPENDENCY":
        module = str(e).split("'")[1] if "'" in str(e) else str(e)
        message = f"Missing Python package: {module}. Railway may need to redeploy to install new dependencies."
    elif code == "BROKER_UNREACHABLE":
        message = "Could not connect to Alpaca. Check API keys and network."
    elif code == "BROKER_TIMEOUT":
        message = "Alpaca API timed out. Try again in a moment."
    elif code == "CLAUDE_TIMEOUT":
        message = "Claude API timed out after 30 seconds. Defaulting to hold."
    elif code == "CLAUDE_API_ERROR":
        message = f"Claude API error: {exc_type}. Check ANTHROPIC_API_KEY."
    elif code == "AUTH_FAILED":
        message = "Authentication failed with a third-party service. Check API keys."
    elif code == "INVALID_RESPONSE":
        message = "Received an invalid response from an external service."
    elif code == "DATA_ERROR":
        # Include the key/field name but not the full traceback
        message = f"Data processing error: {str(e)[:150]}"
    else:
        message = f"Unexpected error ({exc_type}). Check Railway logs for details."

    return {
        "error_code": code,
        "error_type": exc_type,
        "message": message,
    }


@router.get("/bot/status")
def get_bot_status(
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Return bot operational status: scheduler state, active portfolios, last run.

    Portfolio-only model: frequency is the max across active portfolios.
    Strategy details (risk profile, trading goal, kill switch) are per-portfolio
    and surfaced through /portfolios.
    """
    frequency = _max_frequency_among_active(db)
    times = FREQUENCY_SCHEDULES.get(frequency, FREQUENCY_SCHEDULES["1x"])
    time_strs = [f"{h}:{m:02d} ET" for h, m in times]

    last_trade = (
        db.query(Trade)
        .order_by(Trade.timestamp.desc())
        .first()
    )

    next_run = None
    jobs = scheduler.get_jobs()
    trading_jobs = [j for j in jobs if j.id.startswith("trading_cycle_")]
    if trading_jobs:
        next_runs = [j.next_run_time for j in trading_jobs if j.next_run_time]
        if next_runs:
            next_run = min(next_runs).isoformat()

    portfolios = db.query(Portfolio).all()
    active_count = sum(1 for p in portfolios if p.is_active)

    return {
        "running": scheduler.running,
        "frequency": frequency,
        "schedule_times": time_strs,
        "active_portfolios": active_count,
        "total_portfolios": len(portfolios),
        "last_run": last_trade.timestamp.isoformat() if last_trade else None,
        "last_action": last_trade.action if last_trade else None,
        "last_ticker": last_trade.ticker if last_trade else None,
        "next_run": next_run,
        "total_trades": db.query(Trade).filter(Trade.executed.is_(True)).count(),
        "portfolios": [
            {
                "id": p.id,
                "name": p.name,
                "is_active": p.is_active,
                "trading_frequency": p.trading_frequency,
                "trading_goal": p.trading_goal,
                "risk_profile": p.risk_profile,
            }
            for p in portfolios
        ],
    }


@router.get("/admin/errors")
def list_errors(
    limit: int = 20,
    user: dict = Depends(require_auth),
):
    """Return recent errors (most recent first, no stack traces)."""
    return {
        "total": get_error_count(),
        "errors": get_recent_errors(limit),
    }


@router.get("/admin/errors/{ref}")
def get_error(
    ref: str,
    user: dict = Depends(require_auth),
):
    """Look up a specific error by reference code (includes full stack trace)."""
    error = get_error_by_ref(ref)
    if error is None:
        raise HTTPException(status_code=404, detail=f"Error {ref} not found or expired")
    return error


@router.post("/run")
@limiter.limit("2/minute")
async def manual_run(
    request: Request,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Manually trigger one trading cycle across all active portfolios.

    Portfolio-only model: iterates each active portfolio's executor with
    its own strategy. Per-portfolio runs can also be triggered individually
    via POST /portfolios/{id}/run.
    """
    try:
        results = await run_all_plans(db)
        return {
            "portfolios_processed": len(results),
            "results": {pid: [r if isinstance(r, dict) else r.__dict__ for r in rs]
                        for pid, rs in results.items()},
        }
    except Exception as e:
        logger.error("Trading cycle failed: %s\n%s", e, traceback.format_exc())
        error_info = _classify_error(e)
        ref = record_error(
            exception=e,
            path="/run",
            method="POST",
            user_email=user.get("email", ""),
            error_code=error_info["error_code"],
        )
        error_info["ref"] = ref
        raise HTTPException(
            status_code=500,
            detail=error_info,
        )
