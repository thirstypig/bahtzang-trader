"""Backtest API endpoints — CRUD + run."""

import json
import logging
from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import require_auth
from app.database import get_db
from app.backtest.models import BacktestConfig, BacktestResult
from app.backtest.strategies import STRATEGY_REGISTRY, get_strategy_info

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/backtest", tags=["backtest"])


class BacktestCreate(BaseModel):
    name: str = Field(max_length=100)
    strategy: str
    tickers: list[str] = Field(min_length=1, max_length=20)
    start_date: date
    end_date: date
    initial_capital: float = Field(default=100000, gt=0)
    params: dict = Field(default={})
    max_position_pct: float = Field(default=0.10, gt=0, le=1)
    max_positions: int = Field(default=10, gt=0)
    stop_loss_pct: float = Field(default=0.05, gt=0, lt=1)


@router.get("/strategies")
def list_strategies(user: dict = Depends(require_auth)):
    """Return available strategies with their param schemas."""
    return get_strategy_info()


@router.post("/")
async def create_and_run(
    body: BacktestCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Create a backtest and start running it in the background."""
    if body.strategy not in STRATEGY_REGISTRY:
        raise HTTPException(400, f"Unknown strategy: {body.strategy}")
    if body.end_date <= body.start_date:
        raise HTTPException(400, "end_date must be after start_date")

    config = BacktestConfig(
        name=body.name,
        strategy=body.strategy,
        tickers=json.dumps([t.upper() for t in body.tickers]),
        start_date=body.start_date,
        end_date=body.end_date,
        initial_capital=body.initial_capital,
        params=json.dumps(body.params),
        max_position_pct=body.max_position_pct,
        max_positions=body.max_positions,
        stop_loss_pct=body.stop_loss_pct,
    )
    db.add(config)
    db.flush()

    result = BacktestResult(config_id=config.id, status="pending")
    db.add(result)
    db.commit()

    background_tasks.add_task(_run_backtest_bg, config.id, result.id)

    return {
        "config_id": config.id,
        "result_id": result.id,
        "status": "pending",
    }


@router.get("/")
def list_backtests(
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """List all backtests with config + summary metrics."""
    from sqlalchemy.orm import subqueryload

    configs = (
        db.query(BacktestConfig)
        .order_by(BacktestConfig.created_at.desc())
        .all()
    )
    # Batch-load all results in one query instead of N+1
    config_ids = [c.id for c in configs]
    results_map: dict[int, BacktestResult] = {}
    if config_ids:
        results = (
            db.query(BacktestResult)
            .filter(BacktestResult.config_id.in_(config_ids))
            .all()
        )
        results_map = {r.config_id: r for r in results}

    items = []
    for config in configs:
        item = config.to_dict()
        result = results_map.get(config.id)
        if result:
            item.update(result.to_summary())
        items.append(item)
    return items


@router.get("/{result_id}")
def get_result(
    result_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Get full backtest result including equity curve and trades."""
    result = db.query(BacktestResult).filter(BacktestResult.id == result_id).first()
    if not result:
        raise HTTPException(404, "Backtest result not found")

    config = db.query(BacktestConfig).filter(BacktestConfig.id == result.config_id).first()

    data = result.to_detail()
    if config:
        data["config"] = config.to_dict()
    return data


@router.delete("/{config_id}")
def delete_backtest(
    config_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Delete a backtest config and its results."""
    db.query(BacktestResult).filter(BacktestResult.config_id == config_id).delete()
    deleted = db.query(BacktestConfig).filter(BacktestConfig.id == config_id).delete()
    db.commit()
    if not deleted:
        raise HTTPException(404, "Backtest not found")
    return {"status": "deleted"}


def _run_backtest_bg(config_id: int, result_id: int):
    """Background task — creates its own DB session."""
    import asyncio
    from app.database import SessionLocal
    from app.backtest.engine import run_backtest

    db = SessionLocal()
    try:
        config = db.query(BacktestConfig).filter(BacktestConfig.id == config_id).first()
        if config:
            asyncio.run(run_backtest(config, db))
    except Exception as e:
        logger.exception("Background backtest failed: %s", e)
        result = db.query(BacktestResult).filter(BacktestResult.id == result_id).first()
        if result:
            result.status = "failed"
            result.error_message = str(e)
            db.commit()
    finally:
        db.close()
