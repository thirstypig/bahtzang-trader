"""Trading pipeline orchestrator: gather → think → validate → act → log."""

import asyncio
import logging

from sqlalchemy.orm import Session

from app import claude_brain, guardrails, market_data
from app.brokers.schwab import SchwabBroker
from app.logger import log_trade

logger = logging.getLogger(__name__)

DEFAULT_ACCOUNT_ID = "default"

# Broker instance — swap to AlpacaBroker when ready
broker = SchwabBroker()

# Mutex prevents race conditions in concurrent /run requests
_cycle_lock = asyncio.Lock()


async def run_cycle(db: Session, account_id: str = DEFAULT_ACCOUNT_ID) -> dict:
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


async def _execute_cycle(db: Session, account_id: str) -> dict:
    # 1. Gather portfolio state — parallel fetch
    positions, balance = await asyncio.gather(
        broker.get_positions(account_id),
        broker.get_account_balance(account_id),
    )
    cash_available = balance["cash_available"]
    total_invested = balance["total_value"] - cash_available

    # 2. Gather market data — parallel fetch
    held_tickers = [p.get("instrument", {}).get("symbol", "") for p in positions]
    quotes_task = market_data.get_quotes(held_tickers) if held_tickers else asyncio.sleep(0, result=[])
    news_task = market_data.get_news(held_tickers if held_tickers else None)
    quotes, news = await asyncio.gather(quotes_task, news_task)

    # 3. Get Claude's decision
    guardrails_config = guardrails.load_guardrails()
    decision = await claude_brain.get_trade_decision(
        positions=positions,
        cash_available=cash_available,
        market_data=quotes,
        news=news,
        guardrails_config=guardrails_config,
    )

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

    # 4. Run through guardrails
    passed, block_reason = guardrails.check_guardrails(
        decision=decision,
        cash_available=cash_available,
        total_invested=total_invested,
        db=db,
        config=guardrails_config,
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

    return {
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
