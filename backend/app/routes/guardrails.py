"""Guardrails API routes."""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import require_auth
from app.database import get_db
from app.guardrails import (
    RISK_PRESETS,
    TRADING_GOALS,
    GuardrailsUpdate,
    apply_risk_preset,
    load_guardrails,
    save_guardrails,
)
from app.models import GuardrailsAudit
from app import notifier
from app.scheduler import apply_schedule

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/guardrails")
def get_guardrails(
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Current guardrail settings."""
    return load_guardrails(db)


@router.get("/guardrails/presets")
def get_presets(user: dict = Depends(require_auth)):
    """Return all risk profile presets and trading goals."""
    return {"risk_presets": RISK_PRESETS, "trading_goals": TRADING_GOALS}


@router.post("/guardrails")
def update_guardrails(
    config: GuardrailsUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Update guardrail settings."""
    current = load_guardrails(db)

    # If a risk profile is selected, apply the preset as the base
    if config.risk_profile:
        portfolio_value = 100000
        preset = apply_risk_preset(config.risk_profile, portfolio_value)
        preset["kill_switch"] = current.get("kill_switch", False)
        preset["trading_goal"] = current.get("trading_goal", "maximize_returns")
        preset["trading_frequency"] = current.get("trading_frequency", "1x")
        current = preset

    # If a trading goal is selected, auto-suggest matching settings
    if config.trading_goal:
        goal_info = TRADING_GOALS.get(config.trading_goal, {})
        current["trading_goal"] = config.trading_goal
        if not config.trading_frequency:
            current["trading_frequency"] = goal_info.get("recommended_frequency", "1x")

    # Apply any individual overrides on top
    updates = config.model_dump(exclude_none=True, exclude={"risk_profile", "trading_goal"})
    current.update(updates)

    saved = save_guardrails(db, current)

    # Audit log
    changes = config.model_dump(exclude_none=True)
    GuardrailsAudit.log(db, user.get("email", ""), "update", changes)

    # Update scheduler if frequency changed
    apply_schedule(saved.get("trading_frequency", "1x"))

    return saved


@router.post("/killswitch")
async def killswitch(
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Immediately halt all trading."""
    save_guardrails(db, {"kill_switch": True})
    GuardrailsAudit.log(db, user.get("email", ""), "kill_switch_activated", {})
    logger.warning("Kill switch ACTIVATED by %s", user.get("email"))
    await notifier.notify_kill_switch(activated=True, email=user.get("email", ""))
    return {"status": "Kill switch activated", "kill_switch": True}


@router.post("/killswitch/deactivate")
async def killswitch_deactivate(
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Resume trading after kill switch was activated."""
    save_guardrails(db, {"kill_switch": False})
    GuardrailsAudit.log(db, user.get("email", ""), "kill_switch_deactivated", {})
    logger.warning("Kill switch DEACTIVATED by %s", user.get("email"))
    await notifier.notify_kill_switch(activated=False, email=user.get("email", ""))
    return {"status": "Kill switch deactivated — trading resumed", "kill_switch": False}
