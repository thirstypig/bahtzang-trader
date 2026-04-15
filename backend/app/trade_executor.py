"""Trading pipeline orchestrator: gather → think → validate → act → log."""

import asyncio
import logging

from sqlalchemy.orm import Session

from app import claude_brain, guardrails, market_data, notifier
from app.pipeline_types import CycleResult
from app.earnings.client import days_until_earnings, format_earnings_csv
from app.circuit_breaker import check_circuit_breakers, YELLOW, ORANGE, RED
from app.technical_analysis import get_indicators, format_indicators_csv
from app.sector_rotation import get_sector_signals, format_sector_csv
from app.brokers.alpaca import AlpacaBroker
from app.config import settings
from app.logger import log_trade

logger = logging.getLogger(__name__)

DEFAULT_ACCOUNT_ID = "default"

# Primary broker — Alpaca (zero-commission stocks, ETFs, options, crypto)
broker = AlpacaBroker()

# Mutex prevents race conditions in concurrent /run requests
_cycle_lock = asyncio.Lock()


async def run_cycle(db: Session, account_id: str = DEFAULT_ACCOUNT_ID) -> CycleResult:
    """
    Execute one full trading cycle:
    1. Fetch portfolio + balances from broker
    2. Fetch market data + news from Alpha Vantage
    3. Ask Claude for a trade decision
    4. Run decision through guardrails
    5. Execute on broker if approved
    6. Log everything to PostgreSQL
    """
    async with _cycle_lock:
        return await _execute_cycle(db, account_id)


async def _execute_cycle(db: Session, account_id: str) -> CycleResult:
    # 1. Gather portfolio state — parallel fetch
    positions, balance = await asyncio.gather(
        broker.get_positions(account_id),
        broker.get_account_balance(account_id),
    )
    cash_available = balance["cash_available"]
    total_invested = balance["total_value"] - cash_available

    # 1b. Check circuit breakers (before spending Claude API credits)
    guardrails_config = guardrails.load_guardrails(db)
    cb_level, cb_reason = check_circuit_breakers(
        db=db,
        portfolio_value=balance["total_value"],
        config=guardrails_config,
    )
    if cb_level == RED:
        logger.warning("Circuit breaker RED: %s — activating kill switch", cb_reason)
        guardrails.save_guardrails(db, {"kill_switch": True})
        await notifier.notify_kill_switch(activated=True)
        return {
            "trade_id": 0,
            "action": "hold",
            "ticker": "",
            "quantity": 0,
            "price": None,
            "executed": False,
            "guardrail_passed": False,
            "guardrail_block_reason": f"Circuit breaker RED: {cb_reason}",
            "reasoning": cb_reason,
            "confidence": 0,
        }
    if cb_level:
        logger.info("Circuit breaker %s: %s", cb_level, cb_reason)

    # 2. Gather market data + technicals — parallel fetch
    held_tickers = [p.get("instrument", {}).get("symbol", "") for p in positions]
    quotes_task = market_data.get_quotes(held_tickers) if held_tickers else asyncio.sleep(0, result=[])
    news_task = market_data.get_news(held_tickers if held_tickers else None)
    indicators_task = get_indicators(held_tickers) if held_tickers else asyncio.sleep(0, result={})
    sector_task = get_sector_signals()
    quotes, news, indicators, sector_signals = await asyncio.gather(
        quotes_task, news_task, indicators_task, sector_task
    )

    # Format technicals as CSV for Claude
    technicals_csv = format_indicators_csv(indicators)
    sector_csv = format_sector_csv(sector_signals)
    earnings_csv = format_earnings_csv(db, held_tickers) if held_tickers else ""

    # 3. Get Claude's decisions (guardrails_config already loaded in step 1b)
    decisions = await claude_brain.get_trade_decision(
        positions=positions,
        cash_available=cash_available,
        market_data=quotes,
        news=news,
        guardrails_config=guardrails_config,
        technicals_csv=technicals_csv,
        sector_csv=sector_csv,
        earnings_csv=earnings_csv,
    )

    # Process each decision; track remaining cash for multi-trade guardrail checks
    remaining_cash = cash_available
    remaining_invested = total_invested
    current_pos_count = len(positions)
    results: list[CycleResult] = []

    for decision in decisions:
        # Look up current price — check cached quotes first
        price = None
        if decision["ticker"] and decision["action"] != "hold":
            cached = next((q for q in quotes if q["ticker"] == decision["ticker"]), None)
            if cached:
                price = cached["price"]
            else:
                quote = await market_data.get_quote(decision["ticker"])
                price = quote["price"]
            decision["price"] = price

            # Earnings-aware position sizing: cap quantity near earnings
            if decision["action"] == "buy" and price:
                from app.position_sizing import kelly_position_size
                ed = days_until_earnings(db, decision["ticker"])
                max_size = kelly_position_size(
                    confidence=decision.get("confidence", 0.5),
                    portfolio_value=balance["total_value"],
                    db=db,
                    earnings_days=ed,
                )
                if max_size > 0:
                    max_qty = int(max_size / price)
                    if max_qty > 0 and decision["quantity"] > max_qty:
                        logger.info(
                            "Position sizing capped %s from %d to %d shares (earnings in %s days)",
                            decision["ticker"], decision["quantity"], max_qty, ed,
                        )
                        decision["quantity"] = max_qty

        # 4. Run through guardrails (with updated cash/invested from prior trades)
        passed, block_reason = guardrails.check_guardrails(
            decision=decision,
            cash_available=remaining_cash,
            total_invested=remaining_invested,
            db=db,
            config=guardrails_config,
            current_position_count=current_pos_count,
            positions=positions,
        )

        # 5. Execute if approved
        executed = False
        if passed and decision["action"] in ("buy", "sell"):
            try:
                await broker.place_order(
                    account_id=account_id,
                    ticker=decision["ticker"],
                    action=decision["action"],
                    quantity=decision["quantity"],
                )
                executed = True
                trade_value = (price or 0) * decision["quantity"]
                if decision["action"] == "buy":
                    remaining_cash -= trade_value
                    remaining_invested += trade_value
                    current_pos_count += 1
                else:
                    remaining_cash += trade_value
                    remaining_invested -= trade_value
                logger.info(
                    "Executed %s %d shares of %s",
                    decision["action"],
                    decision["quantity"],
                    decision["ticker"],
                )
            except Exception as e:
                logger.error("Order execution failed: %s", e)
                block_reason = f"Execution error: {e}"
                passed = False

        # 6. Log to database
        trade = log_trade(
            db=db,
            ticker=decision.get("ticker", ""),
            action=decision["action"],
            quantity=decision.get("quantity", 0),
            price=price,
            claude_reasoning=decision.get("reasoning"),
            confidence=decision.get("confidence"),
            guardrail_passed=passed,
            guardrail_block_reason=block_reason,
            executed=executed,
        )

        result: CycleResult = {
            "trade_id": trade.id,
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

        # 7. Notify (fire-and-forget — never blocks trading)
        await notifier.notify_trade(result)

    # Return the first result for API compatibility; all trades are logged
    return results[0] if results else {
        "trade_id": 0, "action": "hold", "ticker": "", "quantity": 0,
        "price": None, "executed": False, "guardrail_passed": True,
        "guardrail_block_reason": None, "reasoning": "No decisions", "confidence": 0,
    }
