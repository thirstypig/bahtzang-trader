from sqlalchemy.orm import Session

from app.models import Trade


def log_trade(
    db: Session,
    ticker: str,
    action: str,
    quantity: int,
    price: float | None,
    claude_reasoning: str | None,
    confidence: float | None,
    guardrail_passed: bool,
    guardrail_block_reason: str | None,
    executed: bool,
) -> Trade:
    """Log a trade decision and its outcome to the trades table."""
    trade = Trade(
        ticker=ticker,
        action=action,
        quantity=quantity,
        price=price,
        claude_reasoning=claude_reasoning,
        confidence=confidence,
        guardrail_passed=guardrail_passed,
        guardrail_block_reason=guardrail_block_reason,
        executed=executed,
    )
    db.add(trade)
    db.commit()
    db.refresh(trade)
    return trade
