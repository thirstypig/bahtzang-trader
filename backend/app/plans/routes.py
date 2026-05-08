"""Portfolio API routes — CRUD with budget validation and per-portfolio strategy rules."""

import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import desc, func, text
from sqlalchemy.orm import Session

from app.brokers.alpaca import AlpacaBroker

from app.auth import require_auth
from app.database import get_db
from app.guardrails import VALID_GOALS
from app.models import Trade
from app.plans.executor import compute_virtual_positions
from app.plans.models import Portfolio, PlanSnapshot, PortfolioStrategyAudit

logger = logging.getLogger(__name__)

# Module-level broker instance shared across requests
_broker = AlpacaBroker()

# Advisory lock key for budget validation (arbitrary constant)
_BUDGET_LOCK_KEY = 9001

# 096-fix: Rate limiter for trade-triggering endpoints (real money)
_limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/plans", tags=["plans"])

VALID_PROFILES = "conservative|moderate|aggressive"
VALID_FREQUENCIES = "1x|3x|5x"


class PortfolioCreateRequest(BaseModel):
    name: str = Field(max_length=100)
    budget: float = Field(gt=0, le=10_000_000)
    trading_goal: str = Field(pattern=f"^({VALID_GOALS})$")
    risk_profile: str = Field(default="moderate", pattern=f"^({VALID_PROFILES})$")
    trading_frequency: str = Field(default="1x", pattern=f"^({VALID_FREQUENCIES})$")
    target_amount: float | None = Field(None, gt=0)
    target_date: str | None = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    cooldown_hours: int = Field(default=48, ge=1, le=168)
    min_confidence: float = Field(default=0.55, ge=0, le=1)


class PortfolioUpdateRequest(BaseModel):
    name: str | None = Field(None, max_length=100)
    budget: float | None = Field(None, gt=0, le=10_000_000)
    trading_goal: str | None = Field(None, pattern=f"^({VALID_GOALS})$")
    risk_profile: str | None = Field(None, pattern=f"^({VALID_PROFILES})$")
    trading_frequency: str | None = Field(None, pattern=f"^({VALID_FREQUENCIES})$")
    target_amount: float | None = None
    target_date: str | None = None
    is_active: bool | None = None
    cooldown_hours: int | None = Field(None, ge=1, le=168)
    min_confidence: float | None = Field(None, ge=0, le=1)
    reason: str | None = Field(None, max_length=500)


class StrategyUpdateRequest(BaseModel):
    cooldown_hours: int | None = Field(None, ge=1, le=168)
    min_confidence: float | None = Field(None, ge=0, le=1)
    respect_wash_sale: bool | None = None
    kelly_fraction: float | None = Field(None, ge=0.01, le=1)
    circuit_breaker_daily_pct: float | None = None
    circuit_breaker_weekly_pct: float | None = None
    reason: str = Field(..., max_length=500)


class StrategyAuditEntry(BaseModel):
    id: int
    timestamp: str
    user_email: str
    action: str
    old_value: str | None
    new_value: str | None
    reason: str | None


class StrategyResponse(BaseModel):
    cooldown_hours: int
    min_confidence: float
    respect_wash_sale: bool
    kelly_fraction: float
    circuit_breaker_daily_pct: float
    circuit_breaker_weekly_pct: float
    audit_log: list[StrategyAuditEntry]


def _total_budgets(db: Session, exclude_plan_id: int | None = None) -> float:
    """Sum of all portfolio budgets, optionally excluding one portfolio (for updates)."""
    q = db.query(func.coalesce(func.sum(Portfolio.budget), 0.0))
    if exclude_plan_id is not None:
        q = q.filter(Portfolio.id != exclude_plan_id)
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
def list_portfolios(
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """List all portfolios with summary stats and strategy rules."""
    portfolios = db.query(Portfolio).order_by(Portfolio.created_at.asc()).all()

    # 065-fix: Single GROUP BY query instead of N+1
    counts = dict(
        db.query(Trade.portfolio_id, func.count(Trade.id))
        .filter(Trade.executed.is_(True))
        .group_by(Trade.portfolio_id)
        .all()
    )

    result = []
    for portfolio in portfolios:
        d = portfolio.to_dict()
        d["trade_count"] = counts.get(portfolio.id, 0)
        d["invested"] = float(portfolio.budget) - float(portfolio.virtual_cash)
        # Include strategy summary
        d["strategy"] = {
            "cooldown_hours": portfolio.cooldown_hours,
            "min_confidence": float(portfolio.min_confidence),
            "respect_wash_sale": portfolio.respect_wash_sale,
            "kelly_fraction": float(portfolio.kelly_fraction),
            "circuit_breaker_daily_pct": float(portfolio.circuit_breaker_daily_pct),
            "circuit_breaker_weekly_pct": float(portfolio.circuit_breaker_weekly_pct),
        }
        result.append(d)
    return result


@router.post("")
async def create_portfolio(
    body: PortfolioCreateRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Create a new portfolio with budget validation and strategy audit logging."""
    await _validate_budget(db, body.budget)

    portfolio = Portfolio(
        name=body.name,
        budget=Decimal(str(body.budget)),
        virtual_cash=Decimal(str(body.budget)),  # Starts with full budget as cash
        trading_goal=body.trading_goal,
        risk_profile=body.risk_profile,
        trading_frequency=body.trading_frequency,
        target_amount=Decimal(str(body.target_amount)) if body.target_amount else None,
        target_date=body.target_date,
        cooldown_hours=body.cooldown_hours,
        min_confidence=Decimal(str(body.min_confidence)),
        respect_wash_sale=True,  # Default to True for new portfolios
        kelly_fraction=Decimal("0.15"),  # Default Kelly fraction
        circuit_breaker_daily_pct=Decimal("-5.0"),
        circuit_breaker_weekly_pct=Decimal("-10.0"),
    )
    db.add(portfolio)
    db.commit()
    db.refresh(portfolio)

    # Log initial strategy configuration in audit trail
    initial_strategy = {
        "cooldown_hours": portfolio.cooldown_hours,
        "min_confidence": str(portfolio.min_confidence),
        "respect_wash_sale": portfolio.respect_wash_sale,
        "kelly_fraction": str(portfolio.kelly_fraction),
        "circuit_breaker_daily_pct": str(portfolio.circuit_breaker_daily_pct),
        "circuit_breaker_weekly_pct": str(portfolio.circuit_breaker_weekly_pct),
    }
    audit = PortfolioStrategyAudit(
        portfolio_id=portfolio.id,
        user_email=user.get("email", "unknown"),
        timestamp=datetime.now(timezone.utc),
        action="created",
        old_value=None,
        new_value=str(initial_strategy),
        reason="Portfolio created",
    )
    db.add(audit)
    db.commit()

    logger.info("Created portfolio %d: %s ($%.0f)", portfolio.id, portfolio.name, portfolio.budget)
    return portfolio.to_dict()


@router.get("/{portfolio_id}")
def get_portfolio(
    portfolio_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Get portfolio detail with recent trades."""
    portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
    if not portfolio:
        raise HTTPException(404, "Portfolio not found")

    d = portfolio.to_dict()
    d["invested"] = float(portfolio.budget) - float(portfolio.virtual_cash)

    # Recent trades
    trades = (
        db.query(Trade)
        .filter(Trade.portfolio_id == portfolio_id)
        .order_by(Trade.timestamp.desc())
        .limit(50)
        .all()
    )
    d["trades"] = [t.to_dict() for t in trades]
    return d


@router.get("/{portfolio_id}/positions")
async def get_portfolio_positions(
    portfolio_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Virtual positions with live prices and P&L for a portfolio."""
    portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
    if not portfolio:
        raise HTTPException(404, "Portfolio not found")

    positions = compute_virtual_positions(db, portfolio_id)
    if not positions:
        return []

    # 065-fix: Single aggregated query grouped by ticker instead of N+1
    rows = (
        db.query(
            Trade.ticker,
            func.sum(Trade.quantity * Trade.price).label("total_cost"),
            func.sum(Trade.quantity).label("total_qty"),
        )
        .filter(
            Trade.portfolio_id == portfolio_id,
            Trade.ticker.in_(list(positions.keys())),
            Trade.action == "buy",
            Trade.executed.is_(True),
            Trade.price.isnot(None),
        )
        .group_by(Trade.ticker)
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


@router.patch("/{portfolio_id}")
async def update_portfolio(
    portfolio_id: int,
    body: PortfolioUpdateRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Update portfolio settings with budget re-validation and strategy audit logging."""
    portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
    if not portfolio:
        raise HTTPException(404, "Portfolio not found")

    # 097-fix: Use exclude_unset so explicitly-sent null values (e.g.,
    # target_amount: null) are applied, while omitted fields are skipped.
    updates = body.model_dump(exclude_unset=True)

    # Budget validation if changing budget
    if "budget" in updates:
        new_budget = updates["budget"]
        # 092-fix: Prevent reducing budget below currently invested amount
        # 071-fix: Convert Decimal to float for comparison with Pydantic float
        invested = float(portfolio.budget) - float(portfolio.virtual_cash)
        if new_budget < invested:
            raise HTTPException(
                400,
                f"Cannot reduce budget below invested amount (${invested:,.2f}). "
                "Sell positions first or set a higher budget.",
            )
        await _validate_budget(db, new_budget, exclude_plan_id=portfolio_id)
        # Adjust virtual cash proportionally
        budget_diff = new_budget - float(portfolio.budget)
        portfolio.virtual_cash = max(Decimal("0"), Decimal(str(portfolio.virtual_cash)) + Decimal(str(budget_diff)))
        updates["budget"] = Decimal(str(new_budget))

    # Track strategy changes for audit logging
    strategy_fields = {
        "cooldown_hours", "min_confidence", "respect_wash_sale",
        "kelly_fraction", "circuit_breaker_daily_pct", "circuit_breaker_weekly_pct"
    }
    reason = updates.pop("reason", None)

    # 096-fix: Guard against future mass-assignment if sensitive fields
    # are accidentally added to PortfolioUpdateRequest.
    _IMMUTABLE_FIELDS = {"id", "created_at", "virtual_cash"}
    for key, value in updates.items():
        if key not in _IMMUTABLE_FIELDS:
            # Log strategy field changes to audit trail
            if key in strategy_fields and value is not None:
                old_value = str(getattr(portfolio, key))
                new_value = str(value)
                if old_value != new_value:
                    # Convert float fields to Decimal for storage
                    if key in {"min_confidence", "kelly_fraction", "circuit_breaker_daily_pct", "circuit_breaker_weekly_pct"}:
                        value = Decimal(str(value))
                    audit = PortfolioStrategyAudit(
                        portfolio_id=portfolio_id,
                        user_email=user.get("email", "unknown"),
                        timestamp=datetime.now(timezone.utc),
                        action="strategy_update",
                        old_value=old_value,
                        new_value=new_value,
                        reason=reason,
                    )
                    db.add(audit)
            setattr(portfolio, key, value)

    db.commit()
    db.refresh(portfolio)
    logger.info("Updated portfolio %d: %s", portfolio.id, portfolio.name)
    return portfolio.to_dict()


@router.delete("/{portfolio_id}")
def delete_portfolio(
    portfolio_id: int,
    force: bool = False,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Delete a portfolio. Blocked if executed trades exist unless ?force=true."""
    portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
    if not portfolio:
        raise HTTPException(404, "Portfolio not found")

    # 062-fix: FK is RESTRICT, so delete would fail if trades exist.
    # Surface this as a clear error rather than a raw IntegrityError.
    executed_count = (
        db.query(func.count(Trade.id))
        .filter(Trade.portfolio_id == portfolio_id, Trade.executed.is_(True))
        .scalar()
    )
    if executed_count > 0 and not force:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Portfolio has {executed_count} executed trades. "
                "Export CSV first, then pass ?force=true to permanently delete (trades will be removed)."
            ),
        )

    portfolio_name = portfolio.name
    if force:
        # When forcing, drop all trades first (FK is RESTRICT so manual delete needed)
        db.query(Trade).filter(Trade.portfolio_id == portfolio_id).delete(synchronize_session=False)
    db.delete(portfolio)
    db.commit()

    # 086-fix: Release the per-portfolio asyncio lock to prevent unbounded growth
    from app.plans.executor import _plan_locks
    _plan_locks.pop(portfolio_id, None)

    logger.info("Deleted portfolio %d: %s (force=%s)", portfolio_id, portfolio_name, force)
    return {"status": f"Portfolio '{portfolio_name}' deleted"}


@router.post("/{portfolio_id}/run")
@_limiter.limit("2/minute")
async def run_portfolio(
    request: Request,
    portfolio_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Manually trigger a trading cycle for one portfolio."""
    portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
    if not portfolio:
        raise HTTPException(404, "Portfolio not found")
    if not portfolio.is_active:
        raise HTTPException(400, "Portfolio is paused")

    # 089-fix: Use shared fetch_market_data to include virtual-position tickers.
    # Previously this route only fetched quotes for Alpaca account positions,
    # missing tickers held only in the portfolio's virtual positions.
    from app.plans.executor import fetch_market_data, run_plan_cycle

    positions, balance, quotes, news, technicals_csv, sector_csv, earnings_csv = (
        await fetch_market_data(db, [portfolio_id])
    )

    results = await run_plan_cycle(
        db, portfolio, positions, balance, quotes, news,
        technicals_csv, sector_csv, earnings_csv,
    )
    return results[0] if results else {"action": "hold", "ticker": "", "quantity": 0}


@router.get("/{portfolio_id}/snapshots")
def get_portfolio_snapshots(
    portfolio_id: int,
    days: int = Query(90, ge=1, le=365),
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Return portfolio snapshots for equity curve rendering."""
    portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
    if not portfolio:
        raise HTTPException(404, "Portfolio not found")

    since = date.today() - timedelta(days=days)
    snapshots = (
        db.query(PlanSnapshot)
        .filter(PlanSnapshot.portfolio_id == portfolio_id, PlanSnapshot.date >= since)
        .order_by(PlanSnapshot.date.asc())
        .all()
    )
    return [
        {
            "date": s.date.isoformat(),
            "budget": float(s.budget),
            "virtual_cash": float(s.virtual_cash),
            "invested_value": float(s.invested_value),
            "total_value": float(s.total_value),
            "pnl": float(s.pnl),
            "pnl_pct": float(s.pnl_pct),
        }
        for s in snapshots
    ]


@router.get("/{portfolio_id}/export")
def export_portfolio_trades(
    portfolio_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Export executed portfolio trades as CSV for tax reporting."""
    import csv
    import io
    import re
    from fastapi.responses import StreamingResponse

    portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
    if not portfolio:
        raise HTTPException(404, "Portfolio not found")

    trades = (
        db.query(Trade)
        .filter(Trade.portfolio_id == portfolio_id, Trade.executed.is_(True))
        .order_by(Trade.timestamp.asc())
        .all()
    )

    # 076-fix: Prefix cells starting with formula chars to prevent CSV injection
    def csv_safe(value: str) -> str:
        s = str(value or "")
        if s and s[0] in "=+-@\t\r":
            return "'" + s
        return s

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "Date", "Action", "Ticker", "Quantity", "Price",
        "Total Value", "Confidence", "Virtual Cash After", "Reasoning",
    ])
    for t in trades:
        writer.writerow([
            t.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            csv_safe(t.action.upper()),
            csv_safe(t.ticker),
            f"{t.quantity:.4f}",
            f"{float(t.price):.2f}" if t.price else "",
            f"{float(t.price or 0) * t.quantity:.2f}",
            f"{(t.confidence or 0):.0%}",
            f"{float(t.virtual_cash_after):.2f}" if t.virtual_cash_after is not None else "",
            csv_safe((t.claude_reasoning or "").replace("\n", " ")),
        ])

    buf.seek(0)
    # 077-fix: Strip everything except [a-z0-9-] from filename
    safe_name = re.sub(r"[^a-z0-9\-]", "", portfolio.name.replace(" ", "-").lower())[:50]
    filename = f"bahtzang-{safe_name}-trades.csv"
    return StreamingResponse(
        buf,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{portfolio_id}/strategy", response_model=StrategyResponse)
def get_portfolio_strategy(
    portfolio_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Get current strategy rules and recent audit log for a portfolio."""
    portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
    if not portfolio:
        raise HTTPException(404, "Portfolio not found")

    # Fetch recent audit entries (last 20)
    audit_entries = (
        db.query(PortfolioStrategyAudit)
        .filter(PortfolioStrategyAudit.portfolio_id == portfolio_id)
        .order_by(PortfolioStrategyAudit.timestamp.desc())
        .limit(20)
        .all()
    )

    # Convert to response format
    audit_log = [
        StrategyAuditEntry(
            id=entry.id,
            timestamp=entry.timestamp.isoformat(),
            user_email=entry.user_email,
            action=entry.action,
            old_value=entry.old_value,
            new_value=entry.new_value,
            reason=entry.reason,
        )
        for entry in audit_entries
    ]

    return StrategyResponse(
        cooldown_hours=int(portfolio.cooldown_hours),
        min_confidence=float(portfolio.min_confidence),
        respect_wash_sale=portfolio.respect_wash_sale,
        kelly_fraction=float(portfolio.kelly_fraction),
        circuit_breaker_daily_pct=float(portfolio.circuit_breaker_daily_pct),
        circuit_breaker_weekly_pct=float(portfolio.circuit_breaker_weekly_pct),
        audit_log=audit_log,
    )


@router.post("/{portfolio_id}/strategy", response_model=StrategyResponse)
def update_portfolio_strategy(
    portfolio_id: int,
    update: StrategyUpdateRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Update strategy rules for a portfolio with audit logging."""
    portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
    if not portfolio:
        raise HTTPException(404, "Portfolio not found")

    # Track which fields changed for audit logging
    user_email = user.get("email", "unknown@example.com")

    # Update each provided field and log changes
    if update.cooldown_hours is not None and portfolio.cooldown_hours != update.cooldown_hours:
        old_value = str(portfolio.cooldown_hours)
        portfolio.cooldown_hours = update.cooldown_hours
        db.add(PortfolioStrategyAudit(
            portfolio_id=portfolio_id,
            user_email=user_email,
            action="cooldown_hours",
            old_value=old_value,
            new_value=str(update.cooldown_hours),
            reason=update.reason,
        ))

    if update.min_confidence is not None and portfolio.min_confidence != update.min_confidence:
        old_value = str(float(portfolio.min_confidence))
        portfolio.min_confidence = update.min_confidence
        db.add(PortfolioStrategyAudit(
            portfolio_id=portfolio_id,
            user_email=user_email,
            action="min_confidence",
            old_value=old_value,
            new_value=str(update.min_confidence),
            reason=update.reason,
        ))

    if update.respect_wash_sale is not None and portfolio.respect_wash_sale != update.respect_wash_sale:
        old_value = str(portfolio.respect_wash_sale)
        portfolio.respect_wash_sale = update.respect_wash_sale
        db.add(PortfolioStrategyAudit(
            portfolio_id=portfolio_id,
            user_email=user_email,
            action="respect_wash_sale",
            old_value=old_value,
            new_value=str(update.respect_wash_sale),
            reason=update.reason,
        ))

    if update.kelly_fraction is not None and portfolio.kelly_fraction != update.kelly_fraction:
        old_value = str(float(portfolio.kelly_fraction))
        portfolio.kelly_fraction = update.kelly_fraction
        db.add(PortfolioStrategyAudit(
            portfolio_id=portfolio_id,
            user_email=user_email,
            action="kelly_fraction",
            old_value=old_value,
            new_value=str(update.kelly_fraction),
            reason=update.reason,
        ))

    if update.circuit_breaker_daily_pct is not None and portfolio.circuit_breaker_daily_pct != update.circuit_breaker_daily_pct:
        old_value = str(float(portfolio.circuit_breaker_daily_pct))
        portfolio.circuit_breaker_daily_pct = update.circuit_breaker_daily_pct
        db.add(PortfolioStrategyAudit(
            portfolio_id=portfolio_id,
            user_email=user_email,
            action="circuit_breaker_daily_pct",
            old_value=old_value,
            new_value=str(update.circuit_breaker_daily_pct),
            reason=update.reason,
        ))

    if update.circuit_breaker_weekly_pct is not None and portfolio.circuit_breaker_weekly_pct != update.circuit_breaker_weekly_pct:
        old_value = str(float(portfolio.circuit_breaker_weekly_pct))
        portfolio.circuit_breaker_weekly_pct = update.circuit_breaker_weekly_pct
        db.add(PortfolioStrategyAudit(
            portfolio_id=portfolio_id,
            user_email=user_email,
            action="circuit_breaker_weekly_pct",
            old_value=old_value,
            new_value=str(update.circuit_breaker_weekly_pct),
            reason=update.reason,
        ))

    db.commit()
    db.refresh(portfolio)

    # Fetch updated audit log
    audit_entries = (
        db.query(PortfolioStrategyAudit)
        .filter(PortfolioStrategyAudit.portfolio_id == portfolio_id)
        .order_by(PortfolioStrategyAudit.timestamp.desc())
        .limit(20)
        .all()
    )

    audit_log = [
        StrategyAuditEntry(
            id=entry.id,
            timestamp=entry.timestamp.isoformat(),
            user_email=entry.user_email,
            action=entry.action,
            old_value=entry.old_value,
            new_value=entry.new_value,
            reason=entry.reason,
        )
        for entry in audit_entries
    ]

    return StrategyResponse(
        cooldown_hours=int(portfolio.cooldown_hours),
        min_confidence=float(portfolio.min_confidence),
        respect_wash_sale=portfolio.respect_wash_sale,
        kelly_fraction=float(portfolio.kelly_fraction),
        circuit_breaker_daily_pct=float(portfolio.circuit_breaker_daily_pct),
        circuit_breaker_weekly_pct=float(portfolio.circuit_breaker_weekly_pct),
        audit_log=audit_log,
    )
