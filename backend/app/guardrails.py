import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import Trade

GUARDRAILS_PATH = Path(__file__).resolve().parent.parent / "guardrails.json"


def load_guardrails() -> dict:
    """Load guardrails config from guardrails.json."""
    with open(GUARDRAILS_PATH) as f:
        return json.load(f)


def save_guardrails(config: dict) -> dict:
    """Save updated guardrails config to guardrails.json."""
    with open(GUARDRAILS_PATH, "w") as f:
        json.dump(config, f, indent=2)
    return config


def check_guardrails(
    decision: dict,
    cash_available: float,
    total_invested: float,
    db: Session,
) -> tuple[bool, str | None]:
    """
    Validate a trade decision against all guardrail rules.
    Returns (passed, block_reason).
    """
    config = load_guardrails()

    # Kill switch — block everything
    if config.get("kill_switch", False):
        return False, "Kill switch is active — all trading halted"

    # Hold actions always pass (no trade to validate)
    if decision.get("action") == "hold":
        return True, None

    price = decision.get("price", 0)
    quantity = decision.get("quantity", 0)
    trade_value = price * quantity

    # Max single trade size
    max_single = config.get("max_single_trade_size", 5000)
    if trade_value > max_single:
        return False, f"Trade value ${trade_value:.2f} exceeds max single trade size ${max_single}"

    # Max total invested (only matters for buys)
    if decision.get("action") == "buy":
        max_total = config.get("max_total_invested", 50000)
        if total_invested + trade_value > max_total:
            return (
                False,
                f"Would exceed max total invested: ${total_invested + trade_value:.2f} > ${max_total}",
            )

        # Check cash available
        if trade_value > cash_available:
            return False, f"Insufficient cash: need ${trade_value:.2f}, have ${cash_available:.2f}"

    # Daily order limit
    daily_limit = config.get("daily_order_limit", 10)
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    todays_trades = (
        db.query(Trade)
        .filter(Trade.timestamp >= today_start, Trade.executed.is_(True))
        .count()
    )
    if todays_trades >= daily_limit:
        return False, f"Daily order limit reached ({daily_limit} trades today)"

    # Stop loss threshold — block sells at too large a loss
    # (This is a simplified check; real implementation would compare to entry price)
    stop_loss = config.get("stop_loss_threshold", 0.05)
    if decision.get("action") == "sell" and decision.get("loss_pct", 0) > stop_loss:
        return False, f"Loss {decision['loss_pct']:.1%} exceeds stop-loss threshold {stop_loss:.1%}"

    return True, None
