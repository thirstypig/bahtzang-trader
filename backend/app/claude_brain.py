"""Claude Sonnet trading decision engine."""

import json

import anthropic

from app.config import settings

# 001-fix: Use AsyncAnthropic to avoid blocking the event loop
client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """You are a disciplined trading assistant managing a real brokerage account.
You analyze portfolio positions, cash available, live market data, and news to decide
whether to buy, sell, or hold.

RULES:
- You must respect all guardrails provided. Never suggest trades that violate them.
- Be conservative. Prefer hold over action when uncertain.
- Diversify. Never concentrate more than 20% of the portfolio in a single position.
- Provide clear, concise reasoning for every decision.

You MUST respond with valid JSON only. No markdown, no explanation outside the JSON.
"""


async def get_trade_decision(
    positions: list[dict],
    cash_available: float,
    market_data: list[dict],
    news: list[dict],
    guardrails_config: dict,
) -> dict:
    """Send portfolio context to Claude and get a structured trade decision."""
    user_prompt = json.dumps(
        {
            "portfolio_positions": positions,
            "cash_available": cash_available,
            "market_data": market_data,
            "recent_news": news,
            "guardrails": guardrails_config,
            "instruction": (
                "Analyze the current portfolio, market data, and news. "
                "Decide on ONE action: buy, sell, or hold. "
                "Respond with JSON: {action, ticker, quantity, reasoning, confidence}"
            ),
        },
        indent=2,
    )

    # 001-fix: await the async client
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
