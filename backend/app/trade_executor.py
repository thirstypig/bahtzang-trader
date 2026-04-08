import logging

from sqlalchemy.orm import Session

from app import claude_brain, guardrails, market_data, schwab_client
from app.logger import log_trade

logger = logging.getLogger(__name__)

# TODO: make this configurable per user
DEFAULT_ACCOUNT_ID = "default"


async def run_cycle(db: Session, account_id: str = DEFAULT_ACCOUNT_ID) -> dict:
    """
    Execute one full trading cycle:
    1. Fetch portfolio + balances from Schwab
    2. Fetch market data + news from Alpha Vantage
    3. Ask Claude for a trade decision
    4. Run decision through guardrails
    5. Execute on Schwab if approved
    6. Log everything to PostgreSQL
    """
    # 1. Gather portfolio state
    positions = await schwab_client.get_positions(account_id)
    balance = await schwab_client.get_account_balance(account_id)
    cash_available = balance["cash_available"]
    total_invested = balance["total_value"] - cash_available

    # 2. Gather market data
    held_tickers = [p.get("instrument", {}).get("symbol", "") for p in positions]
    quotes = await market_data.get_quotes(held_tickers) if held_tickers else []
    news = await market_data.get_news(held_tickers if held_tickers else None)

    # 3. Get Claude's decision
    guardrails_config = guardrails.load_guardrails()
    decision = await claude_brain.get_trade_decision(
        positions=positions,
        cash_available=cash_available,
        market_data=quotes,
        news=news,
        guardrails_config=guardrails_config,
    )

    # Look up current price for the decided ticker
    price = None
    if decision["ticker"] and decision["action"] != "hold":
        quote = await market_data.get_quote(decision["ticker"])
        price = quote["price"]
        decision["price"] = price

    # 4. Run through guardrails
    passed, block_reason = guardrails.check_guardrails(
        decision=decision,
        cash_available=cash_available,
        total_invested=total_invested,
        db=db,
    )

    # 5. Execute if approved
    executed = False
    if passed and decision["action"] in ("buy", "sell"):
        try:
            await schwab_client.place_order(
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
