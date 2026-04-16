"""Investment plan API routes — CRUD with budget validation."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import require_auth
from app.database import get_db
from app.plans.models import Plan, PlanTrade

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/plans", tags=["plans"])

VALID_GOALS = "maximize_returns|steady_income|capital_preservation|beat_sp500|swing_trading|passive_index"
VALID_PROFILES = "conservative|moderate|aggressive"
VALID_FREQUENCIES = "1x|3x|5x"


class PlanCreate(BaseModel):
    name: str = Field(max_length=100)
    budget: float = Field(gt=0, le=10_000_000)
    trading_goal: str = Field(pattern=f"^({VALID_GOALS})$")
    risk_profile: str = Field(default="moderate", pattern=f"^({VALID_PROFILES})$")
    trading_frequency: str = Field(default="1x", pattern=f"^({VALID_FREQUENCIES})$")
    target_amount: float | None = Field(None, gt=0)
    target_date: str | None = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")


class PlanUpdate(BaseModel):
    name: str | None = Field(None, max_length=100)
    budget: float | None = Field(None, gt=0, le=10_000_000)
    trading_goal: str | None = Field(None, pattern=f"^({VALID_GOALS})$")
    risk_profile: str | None = Field(None, pattern=f"^({VALID_PROFILES})$")
    trading_frequency: str | None = Field(None, pattern=f"^({VALID_FREQUENCIES})$")
    target_amount: float | None = None
    target_date: str | None = None
    is_active: bool | None = None


def _total_budgets(db: Session, exclude_plan_id: int | None = None) -> float:
    """Sum of all plan budgets, optionally excluding one plan (for updates)."""
    q = db.query(func.coalesce(func.sum(Plan.budget), 0.0))
    if exclude_plan_id:
        q = q.filter(Plan.id != exclude_plan_id)
    return q.scalar()


@router.get("")
def list_plans(
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """List all plans with summary stats."""
    plans = db.query(Plan).order_by(Plan.created_at.asc()).all()
    result = []
    for plan in plans:
        d = plan.to_dict()
        # Add trade count and invested value
        trade_count = (
            db.query(func.count(PlanTrade.id))
            .filter(PlanTrade.plan_id == plan.id, PlanTrade.executed.is_(True))
            .scalar()
        )
        d["trade_count"] = trade_count
        d["invested"] = plan.budget - plan.virtual_cash
        result.append(d)
    return result


@router.post("")
def create_plan(
    body: PlanCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Create a new investment plan with budget validation."""
    existing_total = _total_budgets(db)
    if existing_total + body.budget > 10_000_000:
        raise HTTPException(
            status_code=400,
            detail=f"Total plan budgets (${existing_total + body.budget:,.0f}) would be too high. "
                   f"Existing allocations: ${existing_total:,.0f}.",
        )

    plan = Plan(
        name=body.name,
        budget=body.budget,
        virtual_cash=body.budget,  # Starts with full budget as cash
        trading_goal=body.trading_goal,
        risk_profile=body.risk_profile,
        trading_frequency=body.trading_frequency,
        target_amount=body.target_amount,
        target_date=body.target_date,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    logger.info("Created plan %d: %s ($%.0f)", plan.id, plan.name, plan.budget)
    return plan.to_dict()


@router.get("/{plan_id}")
def get_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Get plan detail with recent trades."""
    plan = db.query(Plan).filter(Plan.id == plan_id).first()
    if not plan:
        raise HTTPException(404, "Plan not found")

    d = plan.to_dict()
    d["invested"] = plan.budget - plan.virtual_cash

    # Recent trades
    trades = (
        db.query(PlanTrade)
        .filter(PlanTrade.plan_id == plan_id)
        .order_by(PlanTrade.timestamp.desc())
        .limit(50)
        .all()
    )
    d["trades"] = [t.to_dict() for t in trades]
    return d


@router.patch("/{plan_id}")
def update_plan(
    plan_id: int,
    body: PlanUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Update plan settings with budget re-validation."""
    plan = db.query(Plan).filter(Plan.id == plan_id).first()
    if not plan:
        raise HTTPException(404, "Plan not found")

    updates = body.model_dump(exclude_none=True)

    # Budget validation if changing budget
    if "budget" in updates:
        other_total = _total_budgets(db, exclude_plan_id=plan_id)
        new_budget = updates["budget"]
        if other_total + new_budget > 10_000_000:
            raise HTTPException(
                400,
                f"Total plan budgets would exceed limit. Other plans: ${other_total:,.0f}.",
            )
        # Adjust virtual cash proportionally
        budget_diff = new_budget - plan.budget
        plan.virtual_cash = max(0, plan.virtual_cash + budget_diff)

    for key, value in updates.items():
        setattr(plan, key, value)

    db.commit()
    db.refresh(plan)
    logger.info("Updated plan %d: %s", plan.id, plan.name)
    return plan.to_dict()


@router.delete("/{plan_id}")
def delete_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Delete a plan (trades are preserved for history)."""
    plan = db.query(Plan).filter(Plan.id == plan_id).first()
    if not plan:
        raise HTTPException(404, "Plan not found")

    plan_name = plan.name
    db.delete(plan)
    db.commit()
    logger.info("Deleted plan %d: %s", plan_id, plan_name)
    return {"status": f"Plan '{plan_name}' deleted"}


@router.post("/{plan_id}/run")
async def run_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Manually trigger a trading cycle for one plan."""
    plan = db.query(Plan).filter(Plan.id == plan_id).first()
    if not plan:
        raise HTTPException(404, "Plan not found")
    if not plan.is_active:
        raise HTTPException(400, "Plan is paused")

    from app.plans.executor import run_plan_cycle
    from app.brokers.alpaca import AlpacaBroker
    from app import market_data, guardrails
    from app.technical_analysis import get_indicators, format_indicators_csv
    from app.sector_rotation import get_sector_signals, format_sector_csv
    from app.earnings.client import format_earnings_csv
    import asyncio

    broker = AlpacaBroker()
    positions, balance = await asyncio.gather(
        broker.get_positions("default"),
        broker.get_account_balance("default"),
    )
    held_tickers = [p.get("instrument", {}).get("symbol", "") for p in positions]
    quotes_task = market_data.get_quotes(held_tickers) if held_tickers else asyncio.sleep(0, result=[])
    news_task = market_data.get_news(held_tickers if held_tickers else None)
    indicators_task = get_indicators(held_tickers) if held_tickers else asyncio.sleep(0, result={})
    sector_task = get_sector_signals()
    quotes, news, indicators, sectors = await asyncio.gather(
        quotes_task, news_task, indicators_task, sector_task
    )

    results = await run_plan_cycle(
        db, plan, positions, balance, quotes, news,
        format_indicators_csv(indicators),
        format_sector_csv(sectors),
        format_earnings_csv(db, held_tickers) if held_tickers else "",
    )
    return results[0] if results else {"action": "hold", "ticker": "", "quantity": 0}


@router.get("/{plan_id}/trades")
def get_plan_trades(
    plan_id: int,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Trade history for a specific plan."""
    plan = db.query(Plan).filter(Plan.id == plan_id).first()
    if not plan:
        raise HTTPException(404, "Plan not found")

    trades = (
        db.query(PlanTrade)
        .filter(PlanTrade.plan_id == plan_id)
        .order_by(PlanTrade.timestamp.desc())
        .limit(limit)
        .all()
    )
    return [t.to_dict() for t in trades]
