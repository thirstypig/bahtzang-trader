"""Charter §3 safety limits, per portfolio, enforced in code (never by prompt).

Two gates, called from the executor:
  evaluate_cycle_limits  start of every cycle: -15% from start → hard stop (portfolio
                         switched off); -3% on the day or -6% on the week → buys halted.
  buy_block_reason       before each buy: halt, ≤8 holdings, ≤2 new buys per day.

Sells are never blocked here — selling is always allowed (charter §3).
Every run path (scheduler, /run, Run Now) reaches these through _execute_plan_cycle.

Days and weeks are US/Eastern calendar days and Monday-start weeks. References come
from the daily PlanSnapshot (taken after the close); a missing snapshot falls back to
the starting budget, so a brand-new portfolio is measured against what it started with.
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app import notifier
from app.models import Trade
from app.plans.models import PlanSnapshot, Portfolio

logger = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")

MAX_HOLDINGS = 8
MAX_NEW_BUYS_PER_DAY = 2
DAILY_HALT_PCT = 0.03
WEEKLY_HALT_PCT = 0.06
HARD_STOP_PCT = 0.15


@dataclass(frozen=True)
class CycleLimits:
    hard_stop: bool
    buy_halt: str | None  # reason text when buys are halted for this cycle


def portfolio_value(
    cash: float, positions: dict[str, float], price_map: dict, avg_costs: dict
) -> float:
    """Cash + holdings at live price, falling back to average cost when unpriced."""
    total = cash
    for ticker, qty in positions.items():
        price = price_map.get(ticker)
        if not price:
            price = avg_costs.get(ticker, 0.0)
            logger.info("No live price for %s — valuing at avg cost %.2f", ticker, price)
        total += qty * price
    return total


def today_et(now: datetime | None = None) -> date:
    return (now or datetime.now(timezone.utc)).astimezone(ET).date()


def _reference(db: Session, plan: Portfolio, before: date) -> float:
    """Latest snapshot value dated strictly before ``before``; else the budget.

    A budget change since the snapshot moved the same amount into or out of cash
    (PATCH budget adjusts virtual_cash), so shift the reference by it — otherwise a
    budget cut reads as a loss and a top-up hides one.
    """
    snap = (
        db.query(PlanSnapshot)
        .filter(PlanSnapshot.portfolio_id == plan.id, PlanSnapshot.date < before)
        .order_by(PlanSnapshot.date.desc())
        .first()
    )
    if snap is None:
        return float(plan.budget)
    return float(snap.total_value) + (float(plan.budget) - float(snap.budget))


def evaluate_cycle_limits(
    db: Session, plan: Portfolio, current_value: float, today: date
) -> CycleLimits:
    start = float(plan.budget)
    if start > 0 and current_value <= start * (1 - HARD_STOP_PCT):
        return CycleLimits(hard_stop=True, buy_halt=None)

    day_ref = _reference(db, plan, today)
    if day_ref > 0:
        day_chg = current_value / day_ref - 1
        if day_chg <= -DAILY_HALT_PCT:
            return CycleLimits(False, (
                f"Daily loss halt: down {day_chg:.1%} since the last close "
                f"(limit -{DAILY_HALT_PCT:.0%}) — no new buys until tomorrow"
            ))

    monday = today - timedelta(days=today.weekday())
    week_ref = _reference(db, plan, monday)
    if week_ref > 0:
        week_chg = current_value / week_ref - 1
        if week_chg <= -WEEKLY_HALT_PCT:
            return CycleLimits(False, (
                f"Weekly loss halt: down {week_chg:.1%} this week "
                f"(limit -{WEEKLY_HALT_PCT:.0%}) — no new buys until next week"
            ))

    return CycleLimits(hard_stop=False, buy_halt=None)


def _buys_today(db: Session, plan: Portfolio, now: datetime) -> int:
    # Trade timestamps are stored as naive UTC; compare against ET midnight in UTC.
    midnight_et = datetime.combine(today_et(now), time.min, tzinfo=ET)
    since = midnight_et.astimezone(timezone.utc).replace(tzinfo=None)
    return (
        db.query(Trade)
        .filter(
            Trade.portfolio_id == plan.id,
            Trade.action == "buy",
            Trade.executed.is_(True),
            Trade.timestamp >= since,
        )
        .count()
    )


def buy_block_reason(
    db: Session,
    plan: Portfolio,
    ticker: str,
    positions: dict[str, float],
    limits: CycleLimits,
    now: datetime,
) -> str | None:
    """Why this buy may not happen, or None if it may."""
    if limits.buy_halt:
        return limits.buy_halt
    held = {t for t, q in positions.items() if q > 1e-9}
    if ticker not in held and len(held) >= MAX_HOLDINGS:
        return f"Max holdings: {len(held)} held (limit {MAX_HOLDINGS}) — no new names"
    bought = _buys_today(db, plan, now)
    if bought >= MAX_NEW_BUYS_PER_DAY:
        return f"Max new buys: {bought} today (limit {MAX_NEW_BUYS_PER_DAY})"
    return None


async def switch_off(db: Session, plan: Portfolio, current_value: float) -> None:
    """Hard stop: turn the portfolio off and say so. Broker-held stops stay in place;
    unwinding is manual (rollback = kill switch + manual unwind)."""
    start = float(plan.budget)
    msg = (
        f"HARD STOP — {plan.name} switched off: value ${current_value:,.0f} is "
        f"{current_value / start - 1:.1%} from its ${start:,.0f} start "
        f"(limit -{HARD_STOP_PCT:.0%}). Broker stops remain; unwind manually."
    )
    plan.is_active = False
    # Audit row: every cycle is logged, and the weekly report counts limit events
    # from the trade ledger.
    db.add(Trade(
        portfolio_id=plan.id, ticker="", action="hold", quantity=0,
        claude_reasoning=msg, guardrail_passed=False, guardrail_block_reason=msg,
        executed=False, virtual_cash_before=plan.virtual_cash,
        virtual_cash_after=plan.virtual_cash,
    ))
    db.commit()
    logger.warning("Plan %d: %s", plan.id, msg)
    await notifier.notify_risk_event(msg)
