"""Trade history API routes."""

from fastapi import APIRouter, Depends, Query
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
