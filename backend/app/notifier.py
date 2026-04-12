"""Slack webhook notifications for trade events."""

import logging
from datetime import datetime, timezone

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_client = httpx.AsyncClient(timeout=10.0)


async def _send_slack(text: str):
    """POST a message to the Slack webhook. Fire-and-forget — never raises."""
    url = settings.SLACK_WEBHOOK_URL
    if not url:
        return

    try:
        resp = await _client.post(url, json={"text": text})
        if resp.status_code != 200:
            logger.warning("Slack webhook returned %d: %s", resp.status_code, resp.text)
    except Exception as e:
        logger.warning("Slack notification failed: %s", e)


async def notify_trade(result: dict):
    """Send notification for a completed trading cycle (executed or blocked)."""
    action = result.get("action", "hold")

    # Don't notify on holds — they're the most common outcome
    if action == "hold":
        return

    executed = result.get("executed", False)
    ticker = result.get("ticker", "")
    quantity = result.get("quantity", 0)
    price = result.get("price")
    confidence = result.get("confidence", 0)
    reasoning = result.get("reasoning", "")

    if executed:
        price_str = f" at ${price:.2f}" if price else ""
        text = (
            f":white_check_mark: *{action.upper()} {quantity} shares {ticker}*{price_str}\n"
            f"Confidence: {confidence:.0%} | {reasoning[:120]}"
        )
    else:
        block_reason = result.get("guardrail_block_reason", "Unknown reason")
        text = (
            f":no_entry: *BLOCKED:* {block_reason}\n"
            f"Would have: {action.upper()} {quantity} {ticker} (confidence {confidence:.0%})"
        )

    await _send_slack(text)


async def notify_kill_switch(activated: bool, email: str = ""):
    """Send notification when kill switch is toggled."""
    if activated:
        text = (
            ":rotating_light: *KILL SWITCH ACTIVATED*\n"
            f"All trading halted. Deactivate at bahtzang.com"
        )
    else:
        text = (
            ":large_green_circle: *KILL SWITCH DEACTIVATED*\n"
            "Trading resumed."
        )
    await _send_slack(text)


async def notify_daily_summary(
    trades_executed: int,
    trades_blocked: int,
    holds: int,
    portfolio_value: float,
    daily_pnl: float,
):
    """Send end-of-day summary."""
    pnl_sign = "+" if daily_pnl >= 0 else ""
    pnl_pct = (daily_pnl / (portfolio_value - daily_pnl)) * 100 if portfolio_value > 0 else 0
    today = datetime.now(timezone.utc).strftime("%b %d, %Y")

    text = (
        f":chart_with_upwards_trend: *Daily Summary — {today}*\n"
        f"Trades: {trades_executed} executed, {trades_blocked} blocked, {holds} holds\n"
        f"Portfolio: ${portfolio_value:,.0f} ({pnl_sign}{pnl_pct:.1f}%)"
    )
    await _send_slack(text)
