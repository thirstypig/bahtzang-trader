"""Trade history API routes."""

import csv
import io

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
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
            "price": t.price,
            "claude_reasoning": t.claude_reasoning,
            "confidence": t.confidence,
            "guardrail_passed": t.guardrail_passed,
            "guardrail_block_reason": t.guardrail_block_reason,
            "executed": t.executed,
        }
        for t in trades
    ]


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
            f"{t.price:.2f}" if t.price else "",
            f"{(t.price or 0) * t.quantity:.2f}",
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
