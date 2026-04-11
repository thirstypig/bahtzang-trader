"""Trading guardrails: safety limits that override Claude's decisions."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.models import Trade

logger = logging.getLogger(__name__)

GUARDRAILS_PATH = Path(__file__).resolve().parent.parent / "guardrails.json"


# Risk profile presets — all values are percentages of portfolio or absolute limits
RISK_PRESETS = {
    "conservative": {
        "max_portfolio_pct": 0.30,       # invest max 30% of portfolio
        "max_single_trade_pct": 0.05,    # max 5% per trade
        "stop_loss_threshold": 0.03,     # 3% stop loss
        "daily_order_limit": 3,
        "min_confidence": 0.75,          # Claude must be 75%+ confident
        "max_positions": 5,
    },
    "moderate": {
        "max_portfolio_pct": 0.60,       # invest max 60% of portfolio
        "max_single_trade_pct": 0.10,    # max 10% per trade
        "stop_loss_threshold": 0.05,     # 5% stop loss
        "daily_order_limit": 5,
        "min_confidence": 0.60,          # Claude must be 60%+ confident
        "max_positions": 10,
    },
    "aggressive": {
        "max_portfolio_pct": 0.90,       # invest max 90% of portfolio
        "max_single_trade_pct": 0.20,    # max 20% per trade
        "stop_loss_threshold": 0.08,     # 8% stop loss
        "daily_order_limit": 10,
        "min_confidence": 0.45,          # Claude can trade at 45%+ confidence
        "max_positions": 20,
    },
}


class GuardrailsUpdate(BaseModel):
    """Validated guardrails update — prevents arbitrary config injection."""
    risk_profile: str | None = Field(None, pattern="^(conservative|moderate|aggressive)$")
    max_total_invested: float | None = Field(None, gt=0, le=10_000_000)
    max_single_trade_size: float | None = Field(None, gt=0, le=1_000_000)
    stop_loss_threshold: float | None = Field(None, gt=0, lt=1)
    daily_order_limit: int | None = Field(None, gt=0, le=100)
    min_confidence: float | None = Field(None, gt=0, le=1)
    max_positions: int | None = Field(None, gt=0, le=100)
    # kill_switch deliberately omitted — only settable via /killswitch


def apply_risk_preset(profile: str, portfolio_value: float = 100000) -> dict:
    """Generate guardrail values from a risk profile preset."""
    preset = RISK_PRESETS.get(profile, RISK_PRESETS["moderate"])
    return {
        "risk_profile": profile,
        "max_total_invested": round(portfolio_value * preset["max_portfolio_pct"]),
        "max_single_trade_size": round(portfolio_value * preset["max_single_trade_pct"]),
        "stop_loss_threshold": preset["stop_loss_threshold"],
        "daily_order_limit": preset["daily_order_limit"],
        "min_confidence": preset["min_confidence"],
        "max_positions": preset["max_positions"],
        "kill_switch": False,
    }


def load_guardrails() -> dict:
    """Load guardrails config from guardrails.json."""
    try:
        with open(GUARDRAILS_PATH) as f:
            config = json.load(f)
            # Ensure new fields have defaults
            config.setdefault("risk_profile", "moderate")
            config.setdefault("min_confidence", 0.60)
            config.setdefault("max_positions", 10)
            return config
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning("Failed to load guardrails, using defaults: %s", e)
        return apply_risk_preset("moderate")


def save_guardrails(config: dict) -> dict:
    """Save updated guardrails config to guardrails.json."""
    try:
        with open(GUARDRAILS_PATH, "w") as f:
            json.dump(config, f, indent=2)
    except OSError as e:
        logger.error("Failed to save guardrails: %s", e)
    return config


def check_guardrails(
    decision: dict,
    cash_available: float,
    total_invested: float,
    db: Session,
    config: dict | None = None,
) -> tuple[bool, str | None]:
    """
    Validate a trade decision against all guardrail rules.
    Returns (passed, block_reason).
    """
    if config is None:
        config = load_guardrails()

    # Kill switch — block everything
    if config.get("kill_switch", False):
        return False, "Kill switch is active — all trading halted"

    # Hold actions always pass (no trade to validate)
    if decision.get("action") == "hold":
        return True, None

    # Minimum confidence check
    min_conf = config.get("min_confidence", 0.60)
    confidence = decision.get("confidence", 0)
    if confidence < min_conf:
        return False, f"Confidence {confidence:.0%} below minimum {min_conf:.0%}"

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

    # Max positions check
    max_positions = config.get("max_positions", 10)
    if decision.get("action") == "buy":
        current_positions = (
            db.query(Trade.ticker)
            .filter(Trade.executed.is_(True), Trade.action == "buy")
            .distinct()
            .count()
        )
        if current_positions >= max_positions:
            return False, f"Max positions reached ({max_positions})"

    return True, None
