"""Daily plan snapshots — captures each active plan's portfolio state."""

import logging
from datetime import date as date_type, timedelta

from sqlalchemy.orm import Session

from app.plans.executor import compute_virtual_positions
from app.technical_analysis import get_indicators
from app.plans.models import Portfolio, PlanSnapshot, TickerPrice

logger = logging.getLogger(__name__)

# How long a carry-forward price stays usable. Long enough to ride out a
# multi-day data outage or a holiday weekend; short enough that a real,
# sustained drawdown can't hide behind an indefinitely repeated stale price.
MAX_CARRY_FORWARD_DAYS = 7


async def take_plan_snapshots(db: Session) -> int:
    """Take a daily snapshot for each active portfolio.

    Computes invested_value from virtual positions x current prices,
    then stores total_value, pnl, and pnl_pct.

    Returns the number of snapshots saved.
    """
    active_plans = db.query(Portfolio).filter(Portfolio.is_active.is_(True)).all()
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

    today = date_type.today()

    # Price every held ticker from Alpaca in one batched request. This is the
    # same source the executor trades on, so snapshots and execution agree.
    price_map: dict[str, float] = {}
    if all_tickers:
        indicators = await get_indicators(sorted(all_tickers))
        for ticker, data in indicators.items():
            price = data.get("price", 0)
            if price > 0:
                price_map[ticker] = price

    # Record every fresh price so it can be carried forward on a future outage.
    for ticker, price in price_map.items():
        cached = db.query(TickerPrice).filter(TickerPrice.ticker == ticker).first()
        if cached:
            cached.price = price
            cached.as_of = today
        else:
            db.add(TickerPrice(ticker=ticker, price=price, as_of=today))

    # Carry forward the last known price for anything the source didn't return.
    # A missing price must never fall through to $0 — that reads as a worthless
    # holding and fabricates a drawdown the portfolio never suffered.
    stale_cutoff = today - timedelta(days=MAX_CARRY_FORWARD_DAYS)
    for ticker in all_tickers - price_map.keys():
        cached = db.query(TickerPrice).filter(TickerPrice.ticker == ticker).first()
        if cached and cached.as_of >= stale_cutoff:
            price_map[ticker] = float(cached.price)
            logger.warning(
                "No live price for %s — carrying forward $%.2f from %s",
                ticker, float(cached.price), cached.as_of,
            )
        else:
            logger.error(
                "No live price for %s and no usable carry-forward (last seen: %s)",
                ticker, cached.as_of if cached else "never",
            )
    db.commit()

    count = 0

    for plan in active_plans:
        positions = all_positions.get(plan.id, {})

        # Refuse to value a portfolio we can't fully price. Writing no row is
        # honest; writing a partial total silently understates the portfolio
        # and would be read as a real loss by the Phase G weekly-P&L gate.
        unpriced = [t for t in positions if t not in price_map]
        if unpriced:
            logger.error(
                "Skipping snapshot for plan %d — unpriced positions: %s",
                plan.id, ", ".join(sorted(unpriced)),
            )
            continue

        # Compute invested value from virtual positions x current prices
        # 071-fix: Convert to float for arithmetic with Decimal plan fields
        invested_value = sum(
            qty * price_map[ticker]
            for ticker, qty in positions.items()
        )

        total_value = invested_value + float(plan.virtual_cash)
        pnl = total_value - float(plan.budget)
        pnl_pct = (pnl / float(plan.budget) * 100) if plan.budget > 0 else 0

        # Upsert: update existing snapshot for today or create new one
        existing = (
            db.query(PlanSnapshot)
            .filter(PlanSnapshot.portfolio_id == plan.id, PlanSnapshot.date == today)
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
                portfolio_id=plan.id,
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
