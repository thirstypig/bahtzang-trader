"""Per-plan trading executor with virtual cash tracking."""

import asyncio
import logging

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app import claude_brain, guardrails, market_data, notifier
from app.pipeline_types import CycleResult
from app.earnings.client import days_until_earnings, format_earnings_csv
from app.circuit_breaker import check_circuit_breakers, RED
from app.technical_analysis import get_indicators, format_indicators_csv
from app.sector_rotation import get_sector_signals, format_sector_csv
from app.brokers.alpaca import AlpacaBroker
from app.models import Trade
from app.plans.models import Plan

logger = logging.getLogger(__name__)

broker = AlpacaBroker()

# 061-fix: Per-plan asyncio locks prevent concurrent runs of the same plan
# from double-spending virtual cash (e.g., scheduler + manual /run collision).
# Broker-level order serialization is handled by `order_lock` in alpaca.py (069-fix).
_plan_locks: dict[int, asyncio.Lock] = {}


def _get_plan_lock(plan_id: int) -> asyncio.Lock:
    """Return the asyncio lock for a given plan_id, creating it on first use."""
    return _plan_locks.setdefault(plan_id, asyncio.Lock())


def compute_virtual_positions(db: Session, plan_id: int) -> dict[str, float]:
    """Compute net shares per ticker from executed trades for a plan."""
    rows = (
        db.query(
            Trade.ticker,
            func.sum(
                case(
                    (Trade.action == "buy", Trade.quantity),
                    (Trade.action == "sell", -Trade.quantity),
                    else_=0,
                )
            ).label("net_qty"),
        )
        .filter(Trade.plan_id == plan_id, Trade.executed.is_(True))
        .group_by(Trade.ticker)
        .all()
    )
    return {row.ticker: row.net_qty for row in rows if row.net_qty > 0}


def _plan_to_guardrails_config(plan: Plan) -> dict:
    """Convert a Plan to a guardrails config dict for Claude.

    071-fix: Convert Decimal fields to float at the boundary — guardrails
    and Claude prompt use float arithmetic throughout.
    """
    from app.guardrails import apply_risk_preset
    budget = float(plan.budget)
    config = apply_risk_preset(plan.risk_profile, budget)
    config["trading_goal"] = plan.trading_goal
    config["trading_frequency"] = plan.trading_frequency
    config["max_total_invested"] = budget
    config["max_single_trade_size"] = min(config["max_single_trade_size"], budget * 0.5)
    config["kill_switch"] = False
    if plan.target_amount:
        config["target_amount"] = float(plan.target_amount)
    if plan.target_date:
        config["target_date"] = plan.target_date
    return config


async def run_plan_cycle(
    db: Session,
    plan: Plan,
    positions: list,
    balance: dict,
    quotes: list,
    news: list,
    technicals_csv: str,
    sector_csv: str,
    earnings_csv: str,
) -> list[CycleResult]:
    """Execute a trading cycle for a single plan using shared market data.

    087-fix: Inlined the per-plan lock (was a separate wrapper/_locked split).
    061-fix: Per-plan lock prevents concurrent runs from double-spending.
    063-fix: Commits each trade individually right after Alpaca order.
    """
    async with _get_plan_lock(plan.id):
        # Re-read plan inside the lock to get the latest virtual_cash
        db.refresh(plan)
        return await _execute_plan_cycle(
            db, plan, positions, balance,
            quotes, news, technicals_csv, sector_csv, earnings_csv,
        )


async def _execute_plan_cycle(
    db: Session,
    plan: Plan,
    positions: list,
    balance: dict,
    quotes: list,
    news: list,
    technicals_csv: str,
    sector_csv: str,
    earnings_csv: str,
) -> list[CycleResult]:

    # Build plan-specific context
    virtual_positions = compute_virtual_positions(db, plan.id)
    plan_config = _plan_to_guardrails_config(plan)

    # 098-fix: Build price lookup dict once instead of O(T) linear scans per ticker
    price_map = {q["ticker"]: q["price"] for q in quotes}

    # Convert virtual positions to the format Claude expects
    plan_positions = [
        {
            "instrument": {"symbol": ticker, "asset_type": "stock"},
            "quantity": qty,
            "market_value": qty * price_map.get(ticker, 0),
            "cost_basis": 0,
            "unrealized_pnl": 0,
            "unrealized_pnl_pct": 0,
        }
        for ticker, qty in virtual_positions.items()
    ]

    # Get Claude's decisions for this plan
    decisions = await claude_brain.get_trade_decision(
        positions=plan_positions,
        cash_available=plan.virtual_cash,
        market_data=quotes,
        news=news,
        guardrails_config=plan_config,
        technicals_csv=technicals_csv,
        sector_csv=sector_csv,
        earnings_csv=earnings_csv,
    )

    results: list[CycleResult] = []
    remaining_cash = plan.virtual_cash

    for decision in decisions:
        price = None
        if decision["ticker"] and decision["action"] != "hold":
            cached_price = price_map.get(decision["ticker"])
            if cached_price is not None:
                price = cached_price
            else:
                quote = await market_data.get_quote(decision["ticker"])
                price = quote["price"]
            decision["price"] = price

            # Position sizing
            if decision["action"] == "buy" and price:
                from app.position_sizing import kelly_position_size
                ed = days_until_earnings(db, decision["ticker"])
                max_size = kelly_position_size(
                    confidence=decision.get("confidence", 0.5),
                    portfolio_value=plan.budget,
                    db=db,
                    earnings_days=ed,
                )
                if max_size > 0:
                    max_qty = int(max_size / price)
                    if max_qty > 0 and decision["quantity"] > max_qty:
                        decision["quantity"] = max_qty

            # SECURITY: Sell validation — prevent cross-plan position theft
            if decision["action"] == "sell":
                plan_qty = virtual_positions.get(decision["ticker"], 0)
                if decision["quantity"] > plan_qty:
                    logger.warning(
                        "Plan %d: sell blocked — owns %.2f of %s, tried to sell %d",
                        plan.id, plan_qty, decision["ticker"], decision["quantity"],
                    )
                    decision["quantity"] = 0
                    decision["action"] = "hold"
                    decision["reasoning"] = f"Sell blocked: plan only owns {plan_qty:.2f} shares"

        # 072-fix: Auto-size buy orders to fractional shares if cash is
        # insufficient. Update the reasoning field so the audit trail reflects
        # the actual quantity (previously Claude's "buy 1 share" would be
        # silently logged as "buy 0.25 share" with unchanged reasoning).
        if decision["action"] == "buy" and price and price > 0:
            trade_value = price * decision.get("quantity", 0)
            # Keep 5% buffer for slippage; minimum $1 order
            max_affordable = max(remaining_cash * 0.95, 0)
            if trade_value > max_affordable and max_affordable >= 1.0:
                new_qty = round(max_affordable / price, 4)
                if new_qty >= 0.0001:
                    original_qty = decision["quantity"]
                    logger.info(
                        "Plan %d: reducing %s qty from %s to %s (cash $%.2f)",
                        plan.id, decision["ticker"], original_qty, new_qty, remaining_cash,
                    )
                    decision["quantity"] = new_qty
                    decision["reasoning"] = (
                        f"{decision.get('reasoning', '')} "
                        f"[Auto-resized from {original_qty} to {new_qty} shares "
                        f"to fit plan cash of ${remaining_cash:.2f}]"
                    ).strip()

        # Guardrail check with plan-scoped values
        trade_value = (price or 0) * decision.get("quantity", 0)
        invested = plan.budget - remaining_cash
        passed = True
        block_reason = None

        if decision["action"] == "buy":
            if trade_value > remaining_cash:
                passed = False
                block_reason = f"Insufficient plan cash: ${remaining_cash:.2f} < ${trade_value:.2f}"
            elif trade_value < 1.0:
                passed = False
                block_reason = f"Trade value $${trade_value:.2f} below $1 minimum"
            elif invested + trade_value > plan.budget:
                passed = False
                block_reason = f"Would exceed plan budget of ${plan.budget:.0f}"
            elif decision.get("confidence", 0) < plan_config.get("min_confidence", 0.6):
                passed = False
                block_reason = f"Confidence {decision.get('confidence', 0):.0%} below minimum {plan_config.get('min_confidence', 0.6):.0%}"

        # 069-fix: Broker-level order_lock handles concurrent order protection;
        # no need for a plan-executor-level lock here.
        executed = False
        alpaca_order_id: str | None = None
        cash_before = remaining_cash
        if passed and decision["action"] in ("buy", "sell") and decision.get("quantity", 0) > 0:
            try:
                # 080-fix: Capture broker return for reconciliation tracking
                order_result = await broker.place_order(
                    account_id="default",
                    ticker=decision["ticker"],
                    action=decision["action"],
                    quantity=decision["quantity"],
                )
                alpaca_order_id = order_result.get("order_id") if order_result else None
                executed = True
                if decision["action"] == "buy":
                    remaining_cash -= trade_value
                else:
                    remaining_cash += trade_value
                logger.info(
                    "Plan %d: executed %s %s shares of %s (Alpaca order %s)",
                    plan.id, decision["action"],
                    decision["quantity"], decision["ticker"], alpaca_order_id,
                )
            except Exception as e:
                logger.error("Plan %d: order failed: %s", plan.id, e)
                block_reason = f"Execution error: {e}"
                passed = False

        # 063-fix: Log trade + update plan cash + commit atomically per decision,
        # immediately after the Alpaca order. This closes the cash-duplication
        # window where a later commit failure would leave a real order unlogged.
        plan_trade = Trade(
            plan_id=plan.id,
            ticker=decision.get("ticker", ""),
            action=decision["action"],
            quantity=decision.get("quantity", 0),
            price=price,
            claude_reasoning=decision.get("reasoning"),
            confidence=decision.get("confidence"),
            guardrail_passed=passed,
            guardrail_block_reason=block_reason,
            executed=executed,
            alpaca_order_id=alpaca_order_id,
            virtual_cash_before=cash_before,
            virtual_cash_after=remaining_cash,
        )
        db.add(plan_trade)
        if executed:
            plan.virtual_cash = remaining_cash
        try:
            db.commit()
            db.refresh(plan_trade)
        except Exception as e:
            db.rollback()
            # 080-fix: Include Alpaca order ID in the reconciliation log
            # so operators can match the executed order to the unwritten state.
            logger.exception(
                "Plan %d: DB commit failed — RECONCILIATION NEEDED. "
                "Alpaca order_id=%s ticker=%s action=%s qty=%s executed=%s. Error: %s",
                plan.id, alpaca_order_id, decision.get("ticker"), decision["action"],
                decision.get("quantity"), executed, e,
            )
            # Re-raise to stop the cycle; other plans continue in run_all_plans
            raise

        result: CycleResult = {
            "trade_id": plan_trade.id,
            "action": decision["action"],
            "ticker": decision.get("ticker", ""),
            "quantity": decision.get("quantity", 0),
            "price": price,
            "executed": executed,
            "guardrail_passed": passed,
            "guardrail_block_reason": block_reason,
            "reasoning": decision.get("reasoning", ""),
            "confidence": decision.get("confidence", 0),
        }
        results.append(result)

    return results


async def fetch_market_data(
    db: Session,
    plan_ids: list[int],
) -> tuple[list, dict, list, list, str, str, str]:
    """Fetch shared market data for one or more plans.

    089-fix: Extracted from run_all_plans so run_plan route can reuse it.
    068-fix: Unions Alpaca account tickers with per-plan virtual position tickers.

    Returns (positions, balance, quotes, news, technicals_csv, sector_csv, earnings_csv).
    """
    positions, balance = await asyncio.gather(
        broker.get_positions("default"),
        broker.get_account_balance("default"),
    )

    # Union account tickers with per-plan virtual position tickers.
    all_tickers = {p.get("instrument", {}).get("symbol", "") for p in positions}
    for pid in plan_ids:
        all_tickers.update(compute_virtual_positions(db, pid).keys())
    all_tickers.discard("")
    held_tickers = sorted(all_tickers)

    quotes_task = market_data.get_quotes(held_tickers) if held_tickers else asyncio.sleep(0, result=[])
    news_task = market_data.get_news(held_tickers if held_tickers else None)
    indicators_task = get_indicators(held_tickers) if held_tickers else asyncio.sleep(0, result={})
    sector_task = get_sector_signals()
    quotes, news, indicators, sector_signals = await asyncio.gather(
        quotes_task, news_task, indicators_task, sector_task
    )
    technicals_csv = format_indicators_csv(indicators)
    sector_csv = format_sector_csv(sector_signals)
    earnings_csv = format_earnings_csv(db, held_tickers) if held_tickers else ""

    return positions, balance, quotes, news, technicals_csv, sector_csv, earnings_csv


async def run_all_plans(db: Session) -> dict[int, list[CycleResult]]:
    """Run trading cycles for all active plans with shared market data."""

    # 1. Check circuit breakers globally first
    global_config = guardrails.load_guardrails(db)
    if global_config.get("kill_switch"):
        logger.info("Kill switch active — skipping all plans")
        return {}

    # 2. Shared data fetch (once for all plans)
    positions_raw, balance = await asyncio.gather(
        broker.get_positions("default"),
        broker.get_account_balance("default"),
    )

    cb_level, cb_reason = check_circuit_breakers(
        db=db, portfolio_value=balance["total_value"], config=global_config,
    )
    if cb_level == RED:
        logger.warning("Circuit breaker RED: %s", cb_reason)
        guardrails.save_guardrails(db, {"kill_switch": True})
        return {}

    # 3. Get active plans FIRST so we can include their tickers in market data
    active_plans = db.query(Plan).filter(Plan.is_active.is_(True)).all()
    if not active_plans:
        logger.info("No active plans")
        return {}

    # 089-fix: Use shared fetch_market_data for consistent ticker union
    positions, balance, quotes, news, technicals_csv, sector_csv, earnings_csv = (
        await fetch_market_data(db, [p.id for p in active_plans])
    )

    # 4. Run each plan's cycle (Claude call happens inside run_plan_cycle).
    # 064-fix: removed wasted asyncio.gather of Claude calls whose results
    # were discarded; run_plan_cycle makes its own Claude call.
    all_results: dict[int, list[CycleResult]] = {}
    for plan in active_plans:
        try:
            results = await run_plan_cycle(
                db, plan, positions, balance,
                quotes, news, technicals_csv, sector_csv, earnings_csv,
            )
            all_results[plan.id] = results
            for r in results:
                await notifier.notify_trade(r)
        except Exception as e:
            logger.exception("Plan %d cycle failed: %s", plan.id, e)
            # Continue with other plans — one plan's failure shouldn't block others

    return all_results
