"""Forex API endpoints — backtest CRUD + run."""

import json
import logging
from datetime import date, datetime, timezone
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import require_auth
from app.database import get_db
from app.forex.models import ForexBacktestRun

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/forex", tags=["forex"])


SUPPORTED_SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD"]


class ForexBacktestCreate(BaseModel):
    name: str = Field(max_length=120)
    symbols: list[str] = Field(min_length=1, max_length=10)
    start_date: date
    end_date: date
    initial_equity: float = Field(default=10_000.0, gt=0)
    risk_pct: float = Field(default=0.02, gt=0, le=0.10)
    sl_buffer_pct: float = Field(default=0.001, ge=0, le=0.05)
    pivot_lookback_weeks: int = Field(default=100, ge=10, le=500)
    cluster_pct: float = Field(default=0.005, gt=0, le=0.05)
    early_exit_mode: Literal["none", "progress", "time_band"] = "none"
    early_exit_min_bars: int = Field(default=10, ge=1, le=200)
    early_exit_threshold_r: float = Field(default=0.3, ge=0.0, le=1.0)


@router.get("/symbols")
def list_supported_symbols(user: dict = Depends(require_auth)):
    return SUPPORTED_SYMBOLS


@router.post("/backtests")
def create_backtest(
    body: ForexBacktestCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    if body.end_date <= body.start_date:
        raise HTTPException(400, "end_date must be after start_date")
    upper_symbols = [s.upper() for s in body.symbols]
    unknown = [s for s in upper_symbols if s not in SUPPORTED_SYMBOLS]
    if unknown:
        raise HTTPException(400, f"Unsupported symbols: {unknown}")

    run = ForexBacktestRun(
        name=body.name,
        status="pending",
        symbols=json.dumps(upper_symbols),
        start_date=body.start_date,
        end_date=body.end_date,
        initial_equity=body.initial_equity,
        risk_pct=body.risk_pct,
        sl_buffer_pct=body.sl_buffer_pct,
        pivot_lookback_weeks=body.pivot_lookback_weeks,
        cluster_pct=body.cluster_pct,
        early_exit_mode=body.early_exit_mode,
        early_exit_min_bars=body.early_exit_min_bars,
        early_exit_threshold_r=body.early_exit_threshold_r,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    background_tasks.add_task(_run_backtest_bg, run.id)

    return {"run_id": run.id, "status": "pending"}


@router.get("/backtests")
def list_backtests(
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    runs = (
        db.query(ForexBacktestRun)
        .order_by(ForexBacktestRun.created_at.desc())
        .all()
    )
    return [r.to_summary() for r in runs]


@router.get("/backtests/{run_id}")
def get_backtest(
    run_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    run = db.query(ForexBacktestRun).filter(ForexBacktestRun.id == run_id).first()
    if not run:
        raise HTTPException(404, "Forex backtest not found")
    return run.to_detail()


@router.delete("/backtests/{run_id}")
def delete_backtest(
    run_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    deleted = db.query(ForexBacktestRun).filter(ForexBacktestRun.id == run_id).delete()
    db.commit()
    if not deleted:
        raise HTTPException(404, "Forex backtest not found")
    return {"status": "deleted"}


def _run_backtest_bg(run_id: int):
    """Background runner — owns its DB session, swallows errors into the row."""
    from app.database import SessionLocal
    from app.forex.engine import run_backtest

    db = SessionLocal()
    try:
        run = db.query(ForexBacktestRun).filter(ForexBacktestRun.id == run_id).first()
        if run is None:
            return
        run.status = "running"
        db.commit()

        symbols = run.get_symbols()
        output = run_backtest(
            symbols=symbols,
            start=run.start_date,
            end=run.end_date,
            initial_equity=run.initial_equity,
            risk_pct=run.risk_pct,
            sl_buffer_pct=run.sl_buffer_pct,
            pivot_lookback_weeks=run.pivot_lookback_weeks,
            cluster_pct=run.cluster_pct,
            early_exit_mode=run.early_exit_mode,
            early_exit_min_bars=run.early_exit_min_bars,
            early_exit_threshold_r=run.early_exit_threshold_r,
            db=db,
        )

        run.status = "completed"
        run.final_equity = output.final_equity
        run.total_return_pct = output.total_return_pct
        run.total_trades = output.total_trades
        run.win_rate_pct = output.win_rate_pct
        run.profit_factor = output.profit_factor
        run.max_drawdown_pct = output.max_drawdown_pct
        run.equity_curve = json.dumps(output.equity_curve)
        run.trades_log = json.dumps(output.trades_log)
        db.commit()
    except Exception as e:
        logger.exception("Forex backtest failed: %s", e)
        try:
            run = db.query(ForexBacktestRun).filter(ForexBacktestRun.id == run_id).first()
            if run is not None:
                run.status = "failed"
                run.error_message = str(e)
                db.commit()
        except Exception:
            db.rollback()
    finally:
        db.close()
