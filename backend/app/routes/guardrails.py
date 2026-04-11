"""Guardrails API routes."""

from fastapi import APIRouter, Depends

from app.auth import require_auth
from app.guardrails import (
    RISK_PRESETS,
    TRADING_GOALS,
    GuardrailsUpdate,
    apply_risk_preset,
    load_guardrails,
    save_guardrails,
)

router = APIRouter()


@router.get("/guardrails")
def get_guardrails(user: dict = Depends(require_auth)):
    """Current guardrail settings."""
    return load_guardrails()


@router.get("/guardrails/presets")
def get_presets(user: dict = Depends(require_auth)):
    """Return all risk profile presets and trading goals."""
    return {"risk_presets": RISK_PRESETS, "trading_goals": TRADING_GOALS}


@router.post("/guardrails")
def update_guardrails(
    config: GuardrailsUpdate,
    user: dict = Depends(require_auth),
):
    """Update guardrail settings."""
    current = load_guardrails()

    # If a risk profile is selected, apply the preset as the base
    if config.risk_profile:
        portfolio_value = current.get("max_total_invested", 100000) / current.get(
            "max_portfolio_pct", 0.60
        ) if "max_portfolio_pct" in current else 100000
        preset = apply_risk_preset(config.risk_profile, portfolio_value)
        preset["kill_switch"] = current.get("kill_switch", False)
        # Preserve goal and frequency
        preset["trading_goal"] = current.get("trading_goal", "maximize_returns")
        preset["trading_frequency"] = current.get("trading_frequency", "1x")
        current = preset

    # If a trading goal is selected, auto-suggest matching settings
    if config.trading_goal:
        goal_info = TRADING_GOALS.get(config.trading_goal, {})
        current["trading_goal"] = config.trading_goal
        # Auto-set frequency if not explicitly overridden
        if not config.trading_frequency:
            current["trading_frequency"] = goal_info.get("recommended_frequency", "1x")

    # Apply any individual overrides on top
    updates = config.model_dump(exclude_none=True, exclude={"risk_profile", "trading_goal"})
    current.update(updates)

    return save_guardrails(current)


@router.post("/killswitch")
def killswitch(user: dict = Depends(require_auth)):
    """Immediately halt all trading."""
    config = load_guardrails()
    config["kill_switch"] = True
    save_guardrails(config)
    return {"status": "Kill switch activated", "kill_switch": True}
