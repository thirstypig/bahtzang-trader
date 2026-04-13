"""Trading guardrails: safety limits that override Claude's decisions."""

import logging
from datetime import datetime, timezone

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.compliance import check_pdt_compliance, check_wash_sale
from app.models import GuardrailsConfig, Trade

logger = logging.getLogger(__name__)


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


TRADING_GOALS = {
    "maximize_returns": {
        "label": "Maximize Returns",
        "recommended_frequency": "3x",
        "recommended_risk": "aggressive",
    },
    "steady_income": {
        "label": "Steady Income",
        "recommended_frequency": "1x",
        "recommended_risk": "conservative",
    },
    "capital_preservation": {
        "label": "Capital Preservation",
        "recommended_frequency": "1x",
        "recommended_risk": "conservative",
    },
    "beat_sp500": {
        "label": "Beat S&P 500",
        "recommended_frequency": "3x",
        "recommended_risk": "moderate",
    },
    "swing_trading": {
        "label": "Swing Trading",
        "recommended_frequency": "5x",
        "recommended_risk": "aggressive",
    },
    "passive_index": {
        "label": "Passive Index",
        "recommended_frequency": "1x",
        "recommended_risk": "conservative",
    },
}

VALID_GOALS = "|".join(TRADING_GOALS.keys())


class GuardrailsUpdate(BaseModel):
    """Validated guardrails update — prevents arbitrary config injection."""
    risk_profile: str | None = Field(None, pattern="^(conservative|moderate|aggressive)$")
    trading_goal: str | None = Field(None, pattern=f"^({VALID_GOALS})$")
    trading_frequency: str | None = Field(None, pattern="^(1x|3x|5x)$")
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
        "trading_goal": "maximize_returns",
        "trading_frequency": "1x",
        "max_total_invested": round(portfolio_value * preset["max_portfolio_pct"]),
        "max_single_trade_size": round(portfolio_value * preset["max_single_trade_pct"]),
        "stop_loss_threshold": preset["stop_loss_threshold"],
        "daily_order_limit": preset["daily_order_limit"],
        "min_confidence": preset["min_confidence"],
        "max_positions": preset["max_positions"],
        "kill_switch": False,
    }


def load_guardrails(db: Session) -> dict:
    """Load guardrails config from the database."""
    config = GuardrailsConfig.get_or_create(db)
    return config.to_dict()


def save_guardrails(db: Session, updates: dict) -> dict:
    """Update guardrails config in the database. Returns the full config dict."""
    config = GuardrailsConfig.get_or_create(db)
    for key, value in updates.items():
        if hasattr(config, key):
            setattr(config, key, value)
    db.commit()
    db.refresh(config)
    return config.to_dict()


def check_guardrails(
    decision: dict,
    cash_available: float,
    total_invested: float,
    db: Session,
    config: dict | None = None,
    current_position_count: int = 0,
) -> tuple[bool, str | None]:
    """
    Validate a trade decision against all guardrail rules.
    Returns (passed, block_reason).
    """
    if config is None:
        config = load_guardrails(db)

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

    # Max positions check — uses actual broker position count
    max_positions = config.get("max_positions", 10)
    if decision.get("action") == "buy":
        if current_position_count >= max_positions:
            return False, f"Max positions reached ({max_positions})"

    # PDT compliance (accounts under $25k)
    if config.get("pdt_protection", True):
        pdt_ok, pdt_msg = check_pdt_compliance(
            db=db,
            account_equity=total_invested + cash_available,
            proposed_action=decision.get("action", "hold"),
            proposed_ticker=decision.get("ticker", ""),
        )
        if not pdt_ok:
            return False, pdt_msg
        if pdt_msg:
            logger.info("PDT: %s", pdt_msg)

    # Wash sale check (warning only, does not block)
    if config.get("respect_wash_sale", True):
        _, wash_msg = check_wash_sale(
            db=db,
            ticker=decision.get("ticker", ""),
            action=decision.get("action", "hold"),
            current_price=decision.get("price"),
        )
        if wash_msg:
            logger.warning("Wash sale: %s", wash_msg)

    return True, None
