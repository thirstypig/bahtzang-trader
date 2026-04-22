"""Daily plan snapshots — captures each active plan's portfolio state."""

import logging
from datetime import date as date_type

from sqlalchemy.orm import Session

from app import market_data
from app.plans.executor import compute_virtual_positions
from app.plans.models import Plan, PlanSnapshot

logger = logging.getLogger(__name__)


async def take_plan_snapshots(db: Session) -> int:
    """Take a daily snapshot for each active plan.

    Computes invested_value from virtual positions x current prices,
    then stores total_value, pnl, and pnl_pct.

    Returns the number of snapshots saved.
    """
    active_plans = db.query(Plan).filter(Plan.is_active.is_(True)).all()
    if not active_plans:
        logger.info("No active plans — skipping plan snapshots")
        return 0

    # Gather all tickers across plans to fetch quotes once
    all_positions: dict[int, dict[str, float]] = {}
    all_tickers: set[str] = set()
    for plan in active_plans:
        vp = compute_virtual_positions(db, plan.id)
        all_positions[plan.id] = vp
        all_tickers.update(vp.keys())

    # Fetch quotes for all tickers at once
    price_map: dict[str, float] = {}
    if all_tickers:
        quotes = await market_data.get_quotes(list(all_tickers))
        for q in quotes:
            price_map[q["ticker"]] = q["price"]

    today = date_type.today()
    count = 0

    for plan in active_plans:
        positions = all_positions.get(plan.id, {})

        # Compute invested value from virtual positions x current prices
        # 071-fix: Convert to float for arithmetic with Decimal plan fields
        invested_value = sum(
            qty * price_map.get(ticker, 0)
            for ticker, qty in positions.items()
        )

        total_value = invested_value + float(plan.virtual_cash)
        pnl = total_value - float(plan.budget)
        pnl_pct = (pnl / float(plan.budget) * 100) if plan.budget > 0 else 0

        # Upsert: update existing snapshot for today or create new one
        existing = (
            db.query(PlanSnapshot)
            .filter(PlanSnapshot.plan_id == plan.id, PlanSnapshot.date == today)
            .first()
        )
        if existing:
            existing.budget = plan.budget
            existing.virtual_cash = plan.virtual_cash
            existing.invested_value = invested_value
            existing.total_value = total_value
            existing.pnl = pnl
            existing.pnl_pct = pnl_pct
        else:
            db.add(PlanSnapshot(
                plan_id=plan.id,
                date=today,
                budget=plan.budget,
                virtual_cash=plan.virtual_cash,
                invested_value=invested_value,
                total_value=total_value,
                pnl=pnl,
                pnl_pct=pnl_pct,
            ))
        count += 1
        logger.info(
            "Plan %d snapshot: total=$%.2f pnl=$%.2f (%.2f%%)",
            plan.id, total_value, pnl, pnl_pct,
        )

    db.commit()
    logger.info("Saved %d plan snapshots for %s", count, today)
    return count
