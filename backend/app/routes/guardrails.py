"""Guardrails API routes."""

from fastapi import APIRouter, Depends

from app.auth import require_auth
from app.guardrails import GuardrailsUpdate, load_guardrails, save_guardrails

router = APIRouter()


@router.get("/guardrails")
def get_guardrails(user: dict = Depends(require_auth)):
    """Current guardrail settings."""
    return load_guardrails()


@router.post("/guardrails")
def update_guardrails(
    config: GuardrailsUpdate,
    user: dict = Depends(require_auth),
):
    """Update guardrail settings. Kill switch cannot be changed here."""
    current = load_guardrails()
    updates = config.model_dump(exclude_none=True)
    current.update(updates)
    return save_guardrails(current)


@router.post("/killswitch")
def killswitch(user: dict = Depends(require_auth)):
    """Immediately halt all trading."""
    config = load_guardrails()
    config["kill_switch"] = True
    save_guardrails(config)
    return {"status": "Kill switch activated", "kill_switch": True}
