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
from app.costs import sell_fees
from app.models import Trade
from app.plans.models import Portfolio

logger = logging.getLogger(__name__)

_LIVE = {"new", "held", "accepted", "pending_new", "partially_filled", "pending_cancel",
         "accepted_for_bidding", "calculated", "pending_replace", "replaced", "done_for_day"}


def covered_qty(db: Session, plan: Portfolio, ticker: str) -> float:
    """Shares of ``ticker`` this portfolio already has an open stop on."""
    return sum(
        (r.stop_qty if r.stop_qty is not None else r.quantity)
        for r in _open_stops(db, plan, ticker)
    )


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
        fee_cost=sell_fees(qty, price),  # spread unknown for a stop fill → NULL
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
    """Apply one broker status to one open stop row. Returns the sell row if shares sold."""
    status = info["status"]
    if status == "filled":
        return await _record_fill(db, plan, row, info)
    if status in _LIVE:
        return None
    # Dead stop. It may have sold part of the position before dying — those shares
    # are gone and must leave the ledger even though the order isn't "filled".
    sell = None
    if info.get("filled_qty") and info.get("filled_avg_price"):
        sell = await _record_fill(db, plan, row, info)
    await _mark_unprotected(db, plan, row, status)
    return sell


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


_GONE = {"canceled", "expired", "rejected"}


async def release_stops(
    db: Session, plan: Portfolio, ticker: str, broker
) -> tuple[bool, float | None]:
    """Cancel this portfolio's open stops on ``ticker`` so a sell can go through.

    Returns (ok_to_sell, highest_cancelled_stop). ok_to_sell is False when a stop
    turned out to have sold shares (the fill is recorded — the position changed, so
    selling now could double-sell), when a cancel did not settle (shares still
    reserved), or when the broker errored. highest_cancelled_stop is returned EVEN
    when ok is False: those stops are gone, and the caller must re-protect whatever
    is still held if the sell does not happen. Never loosen protection.
    """
    ok = True
    highest: float | None = None
    for row in _open_stops(db, plan, ticker):
        try:
            status = await broker.cancel_order(row.stop_order_id)
        except Exception as e:
            logger.warning(
                "Plan %d: cancelling stop %s on %s failed (%s) — sell skipped",
                plan.id, row.stop_order_id, ticker, e,
            )
            ok = False
            break
        info = None
        if status == "filled" or status in _GONE:
            try:
                info = await broker.get_order(row.stop_order_id)
            except Exception as e:
                if status == "filled":
                    # Can't learn the fill size: leave the row open so the next
                    # reconcile records it. Don't sell on top of an unknown fill.
                    logger.warning("Plan %d: fill lookup for %s failed (%s)",
                                   plan.id, row.stop_order_id, e)
                    ok = False
                    continue
                # The stop IS gone — report it so the caller re-protects — but a
                # partial fill can't be ruled out, so block the sell and say so.
                ok = False
                await notifier.notify_risk_event(
                    f"{plan.name}: cancelled stop {row.stop_order_id} on {ticker} but "
                    f"could not check it for a partial fill ({e}) — verify in Alpaca"
                )
        if status == "filled":
            await _record_fill(db, plan, row, info)
            ok = False
        elif status in _GONE:
            if info and info.get("filled_qty") and info.get("filled_avg_price"):
                await _record_fill(db, plan, row, info)  # sold part before the cancel
                ok = False
            row.stop_state = "cancelled"
            db.commit()
            price = float(row.stop_price)
            highest = price if highest is None else max(highest, price)
        else:
            logger.warning(
                "Plan %d: stop %s on %s did not cancel (status %s) — sell skipped",
                plan.id, row.stop_order_id, ticker, status,
            )
            ok = False
    return ok, highest


async def protect_remainder(
    db: Session, plan: Portfolio, sell_trade: Trade, remaining_qty: float,
    stop_price: float, broker,
) -> None:
    """After a partial sell, re-place a GTC stop on the whole shares still held."""
    whole = int(remaining_qty)
    if whole < 1:
        if remaining_qty > 0:
            logger.warning(
                "Plan %d: %.4f %s left after sell is unprotected (under one share)",
                plan.id, remaining_qty, sell_trade.ticker,
            )
        return
    try:
        res = await broker.place_stop_order(sell_trade.ticker, whole, stop_price)
    except Exception as e:
        msg = (
            f"{plan.name}: {whole} {sell_trade.ticker} is UNPROTECTED — "
            f"re-placing its stop at ${stop_price:.2f} failed: {e}"
        )
        logger.error("Plan %d: %s", plan.id, msg)
        await notifier.notify_risk_event(msg)
        return
    sell_trade.stop_order_id = res["order_id"]
    sell_trade.stop_price = stop_price
    sell_trade.stop_qty = whole
    sell_trade.stop_state = "open"
    db.commit()
