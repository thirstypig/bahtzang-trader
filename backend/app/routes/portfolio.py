"""Portfolio API routes."""

import logging
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.analytics import compute_metrics
from app.auth import require_auth
from app.brokers.alpaca import AlpacaBroker
from app.database import get_db
from app.models import PortfolioSnapshot

router = APIRouter()
broker = AlpacaBroker()


@router.get("/portfolio")
async def get_portfolio(user: dict = Depends(require_auth)):
    """Current holdings and cash balance from Alpaca."""
    try:
        account_id = "default"
        positions = await broker.get_positions(account_id)
        balance = await broker.get_account_balance(account_id)
        return {"positions": positions, "balance": balance}
    except Exception as e:
        logging.error("Portfolio fetch failed: %s", e)
        raise HTTPException(status_code=503, detail="Portfolio temporarily unavailable.")


@router.get("/portfolio/snapshots")
def get_snapshots(
    days: int = 90,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Return daily snapshots for charting."""
    cutoff = date.today() - timedelta(days=days)
    snapshots = (
        db.query(PortfolioSnapshot)
        .filter(PortfolioSnapshot.date >= cutoff)
        .order_by(PortfolioSnapshot.date)
        .all()
    )
    return [s.to_dict() for s in snapshots]


@router.get("/portfolio/metrics")
def get_metrics(
    days: int = 90,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Compute and return all portfolio analytics metrics."""
    cutoff = date.today() - timedelta(days=days)
    snapshots = (
        db.query(PortfolioSnapshot)
        .filter(PortfolioSnapshot.date >= cutoff)
        .order_by(PortfolioSnapshot.date)
        .all()
    )

    if len(snapshots) < 2:
        return {
            "error": "insufficient_data",
            "message": f"Need at least 2 daily snapshots. Currently have {len(snapshots)}.",
            "num_snapshots": len(snapshots),
        }

    # 071-fix: Convert Decimal to float — analytics uses float arithmetic
    equities = [float(s.total_equity) for s in snapshots]
    metrics = compute_metrics(equities)
    return metrics.to_dict()


@router.post("/portfolio/snapshot")
async def take_snapshot_now(
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Manually trigger a portfolio snapshot."""
    try:
        balance = await broker.get_account_balance("default")
        positions = await broker.get_positions("default")

        invested = sum(p.get("marketValue", 0) for p in positions)
        unrealized = sum(p.get("currentDayProfitLoss", 0) for p in positions)

        snapshot = PortfolioSnapshot(
            date=date.today(),
            total_equity=balance["total_value"],
            cash=balance["cash_available"],
            invested=invested,
            unrealized_pnl=unrealized,
        )
        db.merge(snapshot)
        db.commit()

        return {
            "status": "Snapshot captured",
            "date": str(date.today()),
            "total_equity": balance["total_value"],
        }
    except Exception as e:
        logging.error("Manual snapshot failed: %s", e)
        raise HTTPException(status_code=500, detail="Snapshot failed. Check server logs.")
