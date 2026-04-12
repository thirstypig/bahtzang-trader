"""Claude Sonnet trading decision engine."""

import json
import logging

import anthropic

from app.config import settings

logger = logging.getLogger(__name__)

client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """You are a disciplined trading assistant managing a real brokerage account.
You analyze portfolio positions, cash available, live market data, and news to decide
whether to buy, sell, or hold.

RULES:
- You must respect all guardrails provided. Never suggest trades that violate them.
- When the TRADING GOAL instruction and RISK PROFILE instruction conflict, the GOAL takes precedence.
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

GOAL_PROMPTS = {
    "maximize_returns": (
        "TRADING GOAL: MAXIMIZE RETURNS (target 15-30% annual). "
        "Seek highest risk-adjusted returns through momentum and factor investing. "
        "Focus on: AAPL, NVDA, MSFT, TSLA, GOOGL, AMZN, META, QQQ, XLK, BTC, ETH. "
        "Look for RSI oversold bounces, MACD positive crossovers, sector momentum leaders. "
        "Hold positions 5-30 days. Maintain 60% buy bias when technicals align. "
        "Keep 20% cash for dip purchases."
    ),
    "steady_income": (
        "TRADING GOAL: STEADY INCOME (target 4-8% annual yield). "
        "Generate income through dividends and covered call premiums. "
        "Focus on high-dividend ETFs and stocks: SCHD, VYM, JEPI, O, JNJ, PG. "
        "Prefer stocks with strong dividend history and sustainable payout ratios. "
        "HOLD 75% of the time. Only trade 1-2x per month. "
        "Never sell within 2 weeks of ex-dividend date. "
        "Sell only when dividend is cut or fundamentals deteriorate."
    ),
    "capital_preservation": (
        "TRADING GOAL: CAPITAL PRESERVATION (target 2-4% annual, minimize losses). "
        "Preserve capital above all. Focus on treasury ETFs and low-volatility stocks. "
        "Focus on: SHV, BIL, XLU, USMV, PG, JNJ. "
        "Maintain minimum 20% cash reserve at all times. "
        "If any position drops > 8%, sell immediately. "
        "Require 80% confidence minimum. HOLD 80% of the time. "
        "Avoid any stock with annualized volatility > 30%."
    ),
    "beat_sp500": (
        "TRADING GOAL: BEAT S&P 500 (outperform SPY by 2-8% annually). "
        "Use tactical sector rotation across 10 sector ETFs. "
        "Focus on: XLK, XLV, XLF, XLE, XLI, XLY, XLP, XLB, XLRE, XLU. "
        "Overweight sectors beating SPY on 3-month relative performance. "
        "Underweight sectors trailing SPY. Rotate once per month, max 3x per month. "
        "Track performance vs SPY daily. Maximum 35% in any single sector."
    ),
    "swing_trading": (
        "TRADING GOAL: SWING TRADING (target 20-40% annual, 2-7 day holds). "
        "Capture 2-5% moves on technical setups. Trade frequently. "
        "Focus on: AAPL, MSFT, NVDA, TSLA, GOOGL, AMD, QQQ, BTC, ETH. "
        "Setups: RSI oversold bounce (<30), MACD bullish crossover, Bollinger breakout. "
        "Take profits at 3-5%. Cut losses at 5% hard stop. "
        "Exit by day 6 regardless (time decay). Max 5 simultaneous positions. "
        "Volume must be 20% above 20-day average for entry."
    ),
    "passive_index": (
        "TRADING GOAL: PASSIVE INDEX (match S&P 500, 8-12% annual). "
        "Buy and hold broad index ETFs. HOLD 99% of the time. "
        "Target allocation: VOO (65%), VTI (25%), VXUS (10%). "
        "Only rebalance when allocation drifts > 5% from target. "
        "Never time the market. Never hold cash (always fully invested). "
        "Ignore VIX, ignore news. Rebalance quarterly at most."
    ),
}

# Fail fast if goal definitions drift between modules
from app.guardrails import TRADING_GOALS  # noqa: E402
assert set(GOAL_PROMPTS.keys()) == set(TRADING_GOALS.keys()), (
    f"GOAL_PROMPTS keys {set(GOAL_PROMPTS.keys())} != TRADING_GOALS keys {set(TRADING_GOALS.keys())}"
)


async def get_trade_decision(
    positions: list[dict],
    cash_available: float,
    market_data: list[dict],
    news: list[dict],
    guardrails_config: dict,
) -> dict:
    """Send portfolio context to Claude and get a structured trade decision."""
    risk_profile = guardrails_config.get("risk_profile", "moderate")
    trading_goal = guardrails_config.get("trading_goal", "maximize_returns")

    risk_instruction = RISK_PROMPTS.get(risk_profile, RISK_PROMPTS["moderate"])
    goal_instruction = GOAL_PROMPTS.get(trading_goal, GOAL_PROMPTS["maximize_returns"])

    # Whitelist guardrail keys passed to Claude to prevent prompt injection
    _SAFE_KEYS = {
        "risk_profile", "trading_goal", "max_total_invested",
        "max_single_trade_size", "stop_loss_threshold", "daily_order_limit",
        "min_confidence", "max_positions", "kill_switch",
    }
    safe_config = {k: v for k, v in guardrails_config.items() if k in _SAFE_KEYS}

    user_prompt = json.dumps(
        {
            "portfolio_positions": positions,
            "cash_available": cash_available,
            "market_data": market_data,
            "recent_news": news,
            "guardrails": safe_config,
            "risk_instruction": risk_instruction,
            "goal_instruction": goal_instruction,
            "instruction": (
                "Analyze the current portfolio, market data, and news. "
                "Decide on ONE action: buy, sell, or hold. "
                f"Minimum confidence to trade: {guardrails_config.get('min_confidence', 0.6)}. "
                "Respond with JSON: {action, ticker, quantity, reasoning, confidence}"
            ),
        },
    )

    try:
        message = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
            timeout=30.0,
        )
    except anthropic.APITimeoutError:
        logger.warning("Claude API timed out after 30s — defaulting to hold")
        return {
            "action": "hold",
            "ticker": "",
            "quantity": 0,
            "reasoning": "Claude API timed out — holding as a safety measure",
            "confidence": 0.0,
        }

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
