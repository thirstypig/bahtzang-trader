"""Claude Sonnet trading decision engine."""

import json

import anthropic

from app.config import settings

client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """You are a disciplined trading assistant managing a real brokerage account.
You analyze portfolio positions, cash available, live market data, and news to decide
whether to buy, sell, or hold.

RULES:
- You must respect all guardrails provided. Never suggest trades that violate them.
- Provide clear, concise reasoning for every decision.
- Your confidence score (0.0-1.0) must honestly reflect your certainty.

You MUST respond with valid JSON only. No markdown, no explanation outside the JSON.
"""

RISK_PROMPTS = {
    "conservative": (
        "RISK PROFILE: CONSERVATIVE. "
        "You strongly prefer HOLD over action. Only trade when you see a very clear, "
        "high-conviction opportunity with minimal downside. Prefer large-cap, stable "
        "stocks. Avoid volatile or speculative positions. Target confidence above 75%. "
        "Preserve capital above all else."
    ),
    "moderate": (
        "RISK PROFILE: MODERATE. "
        "Balance risk and reward. Trade when you see a good opportunity with favorable "
        "risk/reward ratio. Consider both growth and value stocks. Target confidence "
        "above 60%. Maintain diversification across sectors."
    ),
    "aggressive": (
        "RISK PROFILE: AGGRESSIVE. "
        "Actively seek opportunities. You are comfortable with higher volatility and "
        "larger position sizes. Consider momentum plays, growth stocks, and sector "
        "rotation. Trade when confidence is above 45%. Maximize returns while "
        "respecting guardrail limits."
    ),
}


async def get_trade_decision(
    positions: list[dict],
    cash_available: float,
    market_data: list[dict],
    news: list[dict],
    guardrails_config: dict,
) -> dict:
    """Send portfolio context to Claude and get a structured trade decision."""
    risk_profile = guardrails_config.get("risk_profile", "moderate")
    risk_instruction = RISK_PROMPTS.get(risk_profile, RISK_PROMPTS["moderate"])

    user_prompt = json.dumps(
        {
            "portfolio_positions": positions,
            "cash_available": cash_available,
            "market_data": market_data,
            "recent_news": news,
            "guardrails": guardrails_config,
            "risk_instruction": risk_instruction,
            "instruction": (
                "Analyze the current portfolio, market data, and news. "
                "Decide on ONE action: buy, sell, or hold. "
                f"Minimum confidence to trade: {guardrails_config.get('min_confidence', 0.6)}. "
                "Respond with JSON: {action, ticker, quantity, reasoning, confidence}"
            ),
        },
        indent=2,
    )

    message = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    response_text = message.content[0].text

    try:
        decision = json.loads(response_text)
    except json.JSONDecodeError:
        decision = {
            "action": "hold",
            "ticker": "",
            "quantity": 0,
            "reasoning": f"Failed to parse Claude response: {response_text[:200]}",
            "confidence": 0.0,
        }

    return {
        "action": decision.get("action", "hold"),
        "ticker": decision.get("ticker", ""),
        "quantity": decision.get("quantity", 0),
        "reasoning": decision.get("reasoning", ""),
        "confidence": decision.get("confidence", 0.0),
    }
