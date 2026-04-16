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
from app.plans.models import Plan, PlanTrade

logger = logging.getLogger(__name__)

broker = AlpacaBroker()

# Global lock for Alpaca order execution — prevents concurrent orders
_execution_lock = asyncio.Lock()


def compute_virtual_positions(db: Session, plan_id: int) -> dict[str, float]:
    """Compute net shares per ticker from executed PlanTrades."""
    rows = (
        db.query(
            PlanTrade.ticker,
            func.sum(
                case(
                    (PlanTrade.action == "buy", PlanTrade.quantity),
                    (PlanTrade.action == "sell", -PlanTrade.quantity),
                    else_=0,
                )
            ).label("net_qty"),
        )
        .filter(PlanTrade.plan_id == plan_id, PlanTrade.executed.is_(True))
        .group_by(PlanTrade.ticker)
        .all()
    )
    return {row.ticker: row.net_qty for row in rows if row.net_qty > 0}


def _plan_to_guardrails_config(plan: Plan) -> dict:
    """Convert a Plan to a guardrails config dict for Claude."""
    from app.guardrails import apply_risk_preset
    config = apply_risk_preset(plan.risk_profile, plan.budget)
    config["trading_goal"] = plan.trading_goal
    config["trading_frequency"] = plan.trading_frequency
    config["max_total_invested"] = plan.budget
    config["max_single_trade_size"] = min(config["max_single_trade_size"], plan.budget * 0.5)
    config["kill_switch"] = False
    if plan.target_amount:
        config["target_amount"] = plan.target_amount
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
    """Execute a trading cycle for a single plan using shared market data."""

    # Build plan-specific context
    virtual_positions = compute_virtual_positions(db, plan.id)
    plan_config = _plan_to_guardrails_config(plan)

    # Convert virtual positions to the format Claude expects
    plan_positions = [
        {
            "instrument": {"symbol": ticker, "asset_type": "stock"},
            "quantity": qty,
            "market_value": qty * next(
                (q["price"] for q in quotes if q["ticker"] == ticker), 0
            ),
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
            cached = next((q for q in quotes if q["ticker"] == decision["ticker"]), None)
            if cached:
                price = cached["price"]
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

        # Guardrail check with plan-scoped values
        trade_value = (price or 0) * decision.get("quantity", 0)
        invested = plan.budget - remaining_cash
        passed = True
        block_reason = None

        if decision["action"] == "buy":
            if trade_value > remaining_cash:
                passed = False
                block_reason = f"Insufficient plan cash: ${remaining_cash:.2f} < ${trade_value:.2f}"
            elif invested + trade_value > plan.budget:
                passed = False
                block_reason = f"Would exceed plan budget of ${plan.budget:.0f}"
            elif decision.get("confidence", 0) < plan_config.get("min_confidence", 0.6):
                passed = False
                block_reason = f"Confidence {decision.get('confidence', 0):.0%} below minimum {plan_config.get('min_confidence', 0.6):.0%}"

        # Execute under global lock
        executed = False
        cash_before = remaining_cash
        if passed and decision["action"] in ("buy", "sell") and decision.get("quantity", 0) > 0:
            async with _execution_lock:
                try:
                    await broker.place_order(
                        account_id="default",
                        ticker=decision["ticker"],
                        action=decision["action"],
                        quantity=decision["quantity"],
                    )
                    executed = True
                    if decision["action"] == "buy":
                        remaining_cash -= trade_value
                    else:
                        remaining_cash += trade_value
                    logger.info(
                        "Plan %d: executed %s %s shares of %s",
                        plan.id, decision["action"],
                        decision["quantity"], decision["ticker"],
                    )
                except Exception as e:
                    logger.error("Plan %d: order failed: %s", plan.id, e)
                    block_reason = f"Execution error: {e}"
                    passed = False

        # Log to plan_trades
        plan_trade = PlanTrade(
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
            virtual_cash_before=cash_before,
            virtual_cash_after=remaining_cash,
        )
        db.add(plan_trade)
        db.flush()

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

    # Update plan's virtual cash
    plan.virtual_cash = remaining_cash
    db.commit()

    return results


async def run_all_plans(db: Session) -> dict[int, list[CycleResult]]:
    """Run trading cycles for all active plans with shared market data."""

    # 1. Check circuit breakers globally first
    global_config = guardrails.load_guardrails(db)
    if global_config.get("kill_switch"):
        logger.info("Kill switch active — skipping all plans")
        return {}

    # 2. Shared data fetch (once for all plans)
    positions, balance = await asyncio.gather(
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

    held_tickers = [p.get("instrument", {}).get("symbol", "") for p in positions]
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

    # 3. Get active plans
    active_plans = db.query(Plan).filter(Plan.is_active.is_(True)).all()
    if not active_plans:
        logger.info("No active plans")
        return {}

    # 4. Parallel Claude calls, sequential execution
    plan_decisions = await asyncio.gather(*[
        claude_brain.get_trade_decision(
            positions=[
                {"instrument": {"symbol": t, "asset_type": "stock"},
                 "quantity": q, "market_value": q * next((qo["price"] for qo in quotes if qo["ticker"] == t), 0),
                 "cost_basis": 0, "unrealized_pnl": 0, "unrealized_pnl_pct": 0}
                for t, q in compute_virtual_positions(db, plan.id).items()
            ],
            cash_available=plan.virtual_cash,
            market_data=quotes,
            news=news,
            guardrails_config=_plan_to_guardrails_config(plan),
            technicals_csv=technicals_csv,
            sector_csv=sector_csv,
            earnings_csv=earnings_csv,
        )
        for plan in active_plans
    ], return_exceptions=True)

    # 5. Sequential execution per plan
    all_results: dict[int, list[CycleResult]] = {}
    for plan, decisions in zip(active_plans, plan_decisions):
        if isinstance(decisions, Exception):
            logger.error("Plan %d Claude call failed: %s", plan.id, decisions)
            continue
        results = await run_plan_cycle(
            db, plan, positions, balance,
            quotes, news, technicals_csv, sector_csv, earnings_csv,
        )
        all_results[plan.id] = results
        for r in results:
            await notifier.notify_trade(r)

    return all_results
