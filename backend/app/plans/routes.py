"""Investment plan API routes — CRUD with budget validation."""

import logging
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.brokers.alpaca import AlpacaBroker

from app.auth import require_auth
from app.database import get_db
from app.guardrails import VALID_GOALS
from app.plans.executor import compute_virtual_positions
from app.plans.models import Plan, PlanSnapshot, PlanTrade

logger = logging.getLogger(__name__)

# Module-level broker instance shared across requests
_broker = AlpacaBroker()

# Advisory lock key for budget validation (arbitrary constant)
_BUDGET_LOCK_KEY = 9001

router = APIRouter(prefix="/plans", tags=["plans"])

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


async def _validate_budget(db: Session, new_budget: float, exclude_plan_id: int | None = None) -> None:
    """060/081/082-fix: Validate SUM(budgets) + new_budget <= real Alpaca equity.

    - 060: Validates against actual broker equity (not hardcoded cap)
    - 081: Fails closed if broker unreachable — no silent fallback to $10M
    - 082: Uses pg_advisory_xact_lock to prevent concurrent create races

    Caller MUST invoke this inside a transaction that also performs the
    subsequent INSERT, so the advisory lock covers both validation and insert.
    """
    # 082-fix: Advisory lock serializes all budget mutations. Released at
    # transaction end (commit or rollback).
    db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _BUDGET_LOCK_KEY})

    # 081-fix: Fail closed if broker is unreachable. A stale/unknown equity
    # figure would silently allow overallocation.
    try:
        balance = await _broker.get_account_balance("default")
        real_equity = balance.get("total_value", 0)
    except Exception as e:
        logger.warning("Broker unreachable for budget validation: %s", e)
        raise HTTPException(
            status_code=503,
            detail="Broker temporarily unavailable — cannot validate budget against real equity. Try again in a moment.",
        )

    existing_total = _total_budgets(db, exclude_plan_id=exclude_plan_id)
    if existing_total + new_budget > real_equity:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Would exceed account equity. Real equity: ${real_equity:,.2f}, "
                f"existing plan budgets: ${existing_total:,.2f}, "
                f"this plan: ${new_budget:,.2f}."
            ),
        )


@router.get("")
def list_plans(
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """List all plans with summary stats."""
    plans = db.query(Plan).order_by(Plan.created_at.asc()).all()

    # 065-fix: Single GROUP BY query instead of N+1
    counts = dict(
        db.query(PlanTrade.plan_id, func.count(PlanTrade.id))
        .filter(PlanTrade.executed.is_(True))
        .group_by(PlanTrade.plan_id)
        .all()
    )

    result = []
    for plan in plans:
        d = plan.to_dict()
        d["trade_count"] = counts.get(plan.id, 0)
        d["invested"] = plan.budget - plan.virtual_cash
        result.append(d)
    return result


@router.post("")
async def create_plan(
    body: PlanCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Create a new investment plan with budget validation."""
    await _validate_budget(db, body.budget)

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


@router.get("/{plan_id}/positions")
async def get_plan_positions(
    plan_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Virtual positions with live prices and P&L for a plan."""
    plan = db.query(Plan).filter(Plan.id == plan_id).first()
    if not plan:
        raise HTTPException(404, "Plan not found")

    positions = compute_virtual_positions(db, plan_id)
    if not positions:
        return []

    # 065-fix: Single aggregated query grouped by ticker instead of N+1
    rows = (
        db.query(
            PlanTrade.ticker,
            func.sum(PlanTrade.quantity * PlanTrade.price).label("total_cost"),
            func.sum(PlanTrade.quantity).label("total_qty"),
        )
        .filter(
            PlanTrade.plan_id == plan_id,
            PlanTrade.ticker.in_(list(positions.keys())),
            PlanTrade.action == "buy",
            PlanTrade.executed.is_(True),
            PlanTrade.price.isnot(None),
        )
        .group_by(PlanTrade.ticker)
        .all()
    )
    avg_costs: dict[str, float] = {
        r.ticker: (r.total_cost / r.total_qty) if r.total_qty and r.total_qty > 0 else 0.0
        for r in rows
    }

    # Fetch live quotes
    from app import market_data

    tickers = list(positions.keys())
    quotes = await market_data.get_quotes(tickers)
    price_map = {q["ticker"]: q["price"] for q in quotes}

    result = []
    for ticker, qty in positions.items():
        current_price = price_map.get(ticker, 0.0)
        avg_cost = avg_costs.get(ticker, 0.0)
        market_value = qty * current_price
        cost_basis = qty * avg_cost
        pnl = market_value - cost_basis
        pnl_pct = (pnl / cost_basis * 100) if cost_basis > 0 else 0.0

        result.append({
            "ticker": ticker,
            "quantity": qty,
            "avg_cost": round(avg_cost, 2),
            "current_price": round(current_price, 2),
            "market_value": round(market_value, 2),
            "cost_basis": round(cost_basis, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
        })

    # Sort by market value descending
    result.sort(key=lambda x: x["market_value"], reverse=True)
    return result


@router.patch("/{plan_id}")
async def update_plan(
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
        new_budget = updates["budget"]
        await _validate_budget(db, new_budget, exclude_plan_id=plan_id)
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
    force: bool = False,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Delete a plan. Blocked if executed trades exist unless ?force=true."""
    plan = db.query(Plan).filter(Plan.id == plan_id).first()
    if not plan:
        raise HTTPException(404, "Plan not found")

    # 062-fix: FK is RESTRICT, so delete would fail if trades exist.
    # Surface this as a clear error rather than a raw IntegrityError.
    executed_count = (
        db.query(func.count(PlanTrade.id))
        .filter(PlanTrade.plan_id == plan_id, PlanTrade.executed.is_(True))
        .scalar()
    )
    if executed_count > 0 and not force:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Plan has {executed_count} executed trades. "
                "Export CSV first, then pass ?force=true to permanently delete (trades will be removed)."
            ),
        )

    plan_name = plan.name
    if force:
        # When forcing, drop all trades first (FK is RESTRICT so manual delete needed)
        db.query(PlanTrade).filter(PlanTrade.plan_id == plan_id).delete(synchronize_session=False)
    db.delete(plan)
    db.commit()

    # 086-fix: Release the per-plan asyncio lock to prevent unbounded growth
    from app.plans.executor import _plan_locks
    _plan_locks.pop(plan_id, None)

    logger.info("Deleted plan %d: %s (force=%s)", plan_id, plan_name, force)
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


@router.get("/{plan_id}/snapshots")
def get_plan_snapshots(
    plan_id: int,
    days: int = 90,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Return plan snapshots for equity curve rendering."""
    plan = db.query(Plan).filter(Plan.id == plan_id).first()
    if not plan:
        raise HTTPException(404, "Plan not found")

    since = date.today() - timedelta(days=days)
    snapshots = (
        db.query(PlanSnapshot)
        .filter(PlanSnapshot.plan_id == plan_id, PlanSnapshot.date >= since)
        .order_by(PlanSnapshot.date.asc())
        .all()
    )
    return [
        {
            "date": s.date.isoformat(),
            "budget": s.budget,
            "virtual_cash": s.virtual_cash,
            "invested_value": s.invested_value,
            "total_value": s.total_value,
            "pnl": s.pnl,
            "pnl_pct": s.pnl_pct,
        }
        for s in snapshots
    ]


@router.get("/{plan_id}/metrics")
def get_plan_metrics(
    plan_id: int,
    days: int = 90,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Computed analytics for a plan: total return, best/worst day, trading days."""
    plan = db.query(Plan).filter(Plan.id == plan_id).first()
    if not plan:
        raise HTTPException(404, "Plan not found")

    since = date.today() - timedelta(days=days)
    snapshots = (
        db.query(PlanSnapshot)
        .filter(PlanSnapshot.plan_id == plan_id, PlanSnapshot.date >= since)
        .order_by(PlanSnapshot.date.asc())
        .all()
    )

    num_trading_days = len(snapshots)

    if num_trading_days == 0:
        return {
            "total_return_pct": 0,
            "best_day_pct": 0,
            "worst_day_pct": 0,
            "num_trading_days": 0,
        }

    # Total return from first snapshot to last
    first = snapshots[0]
    last = snapshots[-1]
    total_return_pct = (
        ((last.total_value - first.budget) / first.budget * 100)
        if first.budget > 0
        else 0
    )

    # Daily returns (day-over-day pnl_pct change)
    daily_changes: list[float] = []
    for i in range(1, len(snapshots)):
        prev_val = snapshots[i - 1].total_value
        curr_val = snapshots[i].total_value
        if prev_val > 0:
            daily_changes.append((curr_val - prev_val) / prev_val * 100)

    best_day_pct = max(daily_changes) if daily_changes else 0
    worst_day_pct = min(daily_changes) if daily_changes else 0

    return {
        "total_return_pct": round(total_return_pct, 2),
        "best_day_pct": round(best_day_pct, 2),
        "worst_day_pct": round(worst_day_pct, 2),
        "num_trading_days": num_trading_days,
    }


@router.get("/{plan_id}/export")
def export_plan_trades(
    plan_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Export executed plan trades as CSV for tax reporting."""
    import csv
    import io
    from fastapi.responses import StreamingResponse

    plan = db.query(Plan).filter(Plan.id == plan_id).first()
    if not plan:
        raise HTTPException(404, "Plan not found")

    trades = (
        db.query(PlanTrade)
        .filter(PlanTrade.plan_id == plan_id, PlanTrade.executed.is_(True))
        .order_by(PlanTrade.timestamp.asc())
        .all()
    )

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "Date", "Action", "Ticker", "Quantity", "Price",
        "Total Value", "Confidence", "Virtual Cash After", "Reasoning",
    ])
    for t in trades:
        writer.writerow([
            t.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            t.action.upper(),
            t.ticker,
            f"{t.quantity:.4f}",
            f"{t.price:.2f}" if t.price else "",
            f"{(t.price or 0) * t.quantity:.2f}",
            f"{(t.confidence or 0):.0%}",
            f"{t.virtual_cash_after:.2f}",
            (t.claude_reasoning or "").replace("\n", " "),
        ])

    buf.seek(0)
    safe_name = plan.name.replace(" ", "-").lower()
    filename = f"bahtzang-{safe_name}-trades.csv"
    return StreamingResponse(
        buf,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
