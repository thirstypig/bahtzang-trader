"""Broker-held stop lifecycle, kept in step with the virtual ledger.

Every risk-engine buy carries a GTC stop at Alpaca, recorded on its Trade row
(stop_order_id, stop_price, stop_state="open"). That stop acts on its own — at 11:42 AM
when nothing here is awake — so the ledger has to be told:

  reconcile_stops   start of every cycle: record fired stops as sells, flag stops that
                    vanished (cancelled outside the system) as UNPROTECTED.
  release_stops     before a sell: cancel THIS portfolio's legs (Alpaca reserves the
                    shares for them, so the sell would be rejected). Never touches
                    another portfolio's stops in the shared account.
  protect_remainder after a partial sell: put a fresh stop on the whole shares left.

A stop that cannot be confirmed is left "open" and checked again next cycle; it is
never guessed into a state.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app import notifier
from app.models import Trade
from app.plans.models import Portfolio

logger = logging.getLogger(__name__)

_LIVE = {"new", "held", "accepted", "pending_new", "partially_filled", "pending_cancel",
         "accepted_for_bidding", "calculated", "pending_replace", "replaced", "done_for_day"}


def _open_stops(db: Session, plan: Portfolio, ticker: str | None = None) -> list[Trade]:
    q = db.query(Trade).filter(Trade.portfolio_id == plan.id, Trade.stop_state == "open")
    if ticker is not None:
        q = q.filter(Trade.ticker == ticker)
    return q.order_by(Trade.id).all()


async def _record_fill(db: Session, plan: Portfolio, row: Trade, info: dict) -> Trade:
    """The stop sold shares at the broker — write the sell and credit the cash."""
    qty = float(info["filled_qty"])
    price = float(info["filled_avg_price"])
    cash_before = float(plan.virtual_cash)
    cash_after = cash_before + qty * price
    sell = Trade(
        portfolio_id=plan.id,
        ticker=row.ticker,
        action="sell",
        quantity=qty,
        price=price,
        claude_reasoning=(
            f"Broker stop fired: {qty:g} {row.ticker} sold at ${price:.2f} "
            f"(stop ${float(row.stop_price):.2f}, from trade #{row.id})"
        ),
        guardrail_passed=True,
        executed=True,
        alpaca_order_id=row.stop_order_id,
        virtual_cash_before=cash_before,
        virtual_cash_after=cash_after,
        timestamp=datetime.now(timezone.utc),
    )
    db.add(sell)
    row.stop_state = "filled"
    plan.virtual_cash = cash_after
    db.commit()
    db.refresh(sell)
    logger.info("Plan %d: stop fired — %s", plan.id, sell.claude_reasoning)
    await notifier.notify_risk_event(f"{plan.name}: {sell.claude_reasoning}")
    return sell


async def _mark_unprotected(db: Session, plan: Portfolio, row: Trade, status: str) -> None:
    row.stop_state = "cancelled"
    db.commit()
    msg = (
        f"{plan.name}: {row.ticker} is UNPROTECTED — its broker stop "
        f"{row.stop_order_id} is {status} and was not cancelled by the bot"
    )
    logger.warning("Plan %d: %s", plan.id, msg)
    await notifier.notify_risk_event(msg)


async def _settle(db: Session, plan: Portfolio, row: Trade, info: dict) -> Trade | None:
    """Apply one broker status to one open stop row. Returns the sell row if it fired."""
    status = info["status"]
    if status == "filled":
        return await _record_fill(db, plan, row, info)
    if status in _LIVE:
        return None
    await _mark_unprotected(db, plan, row, status)
    return None


async def reconcile_stops(db: Session, plan: Portfolio, broker) -> list[Trade]:
    """Bring every open stop of this portfolio up to date. Returns the sells inserted."""
    inserted: list[Trade] = []
    for row in _open_stops(db, plan):
        try:
            info = await broker.get_order(row.stop_order_id)
        except Exception as e:
            logger.warning(
                "Plan %d: could not check stop %s (%s) — will retry next cycle",
                plan.id, row.stop_order_id, e,
            )
            continue
        sell = await _settle(db, plan, row, info)
        if sell is not None:
            inserted.append(sell)
    return inserted
