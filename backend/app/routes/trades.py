"""Trade history API routes."""

import csv
import io
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import require_auth
from app.database import get_db
from app.models import Trade

router = APIRouter()


@router.get("/trades")
def get_trades(
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Full trade history with decisions and reasoning."""
    trades = (
        db.query(Trade).order_by(Trade.timestamp.desc()).limit(limit).all()
    )
    return [
        {
            "id": t.id,
            "timestamp": t.timestamp.isoformat(),
            "ticker": t.ticker,
            "action": t.action,
            "quantity": t.quantity,
            "price": float(t.price) if t.price is not None else None,
            "claude_reasoning": t.claude_reasoning,
            "confidence": t.confidence,
            "guardrail_passed": t.guardrail_passed,
            "guardrail_block_reason": t.guardrail_block_reason,
            "executed": t.executed,
        }
        for t in trades
    ]


@router.get("/trades/summary")
def get_trades_summary(
    limit: int = Query(500, ge=1, le=1000),
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Lightweight trade history for analytics — excludes reasoning text."""
    trades = (
        db.query(
            Trade.id, Trade.timestamp, Trade.ticker, Trade.action,
            Trade.quantity, Trade.price, Trade.confidence,
            Trade.guardrail_passed, Trade.executed,
        )
        .order_by(Trade.timestamp.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": t.id,
            "timestamp": t.timestamp.isoformat(),
            "ticker": t.ticker,
            "action": t.action,
            "quantity": t.quantity,
            "price": float(t.price) if t.price is not None else None,
            "confidence": t.confidence,
            "guardrail_passed": t.guardrail_passed,
            "executed": t.executed,
        }
        for t in trades
    ]


@router.get("/trades/block-stats")
def get_block_stats(
    days: int = Query(14, ge=1, le=90),
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Aggregate guardrail-block reasons over the last N days.

    Used to verify that recent fixes (zero-qty coercion, headroom prompt)
    actually reduced the dominant block reasons in production. Replaces
    the manual Supabase SQL query in the verify-block-rate-drop todo.

    Returns a list of {reason, count, last_seen} sorted by count desc, plus
    a totals summary.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    rows = (
        db.query(
            Trade.guardrail_block_reason,
            func.count().label("count"),
            func.max(Trade.timestamp).label("last_seen"),
        )
        .filter(
            Trade.guardrail_passed.is_(False),
            Trade.timestamp >= cutoff,
            Trade.guardrail_block_reason.isnot(None),
        )
        .group_by(Trade.guardrail_block_reason)
        .order_by(func.count().desc())
        .all()
    )

    total_blocks = sum(r.count for r in rows)
    # `.scalar()` can return None on some DB backends with no rows — coalesce
    # to 0 so the ratio calc below doesn't TypeError on None comparison.
    total_executed = (
        db.query(func.count())
        .select_from(Trade)
        .filter(Trade.executed.is_(True), Trade.timestamp >= cutoff)
        .scalar()
    ) or 0
    total_decisions = (
        db.query(func.count())
        .select_from(Trade)
        .filter(Trade.timestamp >= cutoff)
        .scalar()
    ) or 0

    return {
        "window_days": days,
        "since": cutoff.isoformat(),
        "total_decisions": total_decisions,
        "total_executed": total_executed,
        "total_blocked": total_blocks,
        "block_rate_pct": round(100 * total_blocks / total_decisions, 2) if total_decisions else 0,
        "by_reason": [
            {
                "reason": r.guardrail_block_reason,
                "count": r.count,
                "last_seen": r.last_seen.isoformat() if r.last_seen else None,
            }
            for r in rows
        ],
    }


@router.get("/trades/export")
def export_trades(
    year: int | None = Query(None, ge=2020, le=2100),
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Export executed trades as CSV for tax reporting."""
    query = db.query(Trade).filter(Trade.executed.is_(True))
    if year:
        from sqlalchemy import extract
        query = query.filter(extract("year", Trade.timestamp) == year)
    trades = query.order_by(Trade.timestamp.asc()).all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "Date", "Action", "Ticker", "Quantity", "Price",
        "Total Value", "Confidence", "Reasoning",
    ])
    # 076-fix: Prefix cells starting with formula chars to prevent CSV injection
    def csv_safe(value: str) -> str:
        s = str(value or "")
        if s and s[0] in "=+-@\t\r":
            return "'" + s
        return s

    for t in trades:
        writer.writerow([
            t.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            csv_safe(t.action.upper()),
            csv_safe(t.ticker),
            t.quantity,
            f"{float(t.price):.2f}" if t.price else "",
            f"{float(t.price or 0) * t.quantity:.2f}",
            f"{(t.confidence or 0):.0%}",
            csv_safe((t.claude_reasoning or "").replace("\n", " ")),
        ])

    buf.seek(0)
    filename = f"bahtzang-trades-{year or 'all'}.csv"
    return StreamingResponse(
        buf,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
