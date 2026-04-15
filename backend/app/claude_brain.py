"""Claude Sonnet trading decision engine."""

import json
import logging

import anthropic

from app.config import settings
from app.pipeline_types import Position, Quote, NewsItem, TradeDecision

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
        "Consider high-dividend ETFs and stocks like SCHD, VYM, JEPI, O, JNJ, PG. "
        "IMPORTANT: Verify current dividend yields from the market data provided — "
        "do not assume historical yields are still accurate. "
        "Prefer stocks with strong dividend history and sustainable payout ratios. "
        "HOLD 75% of the time. Only trade 1-2x per month. "
        "Never sell within 2 weeks of ex-dividend date. "
        "Sell only when dividend is cut or fundamentals deteriorate."
    ),
    "capital_preservation": (
        "TRADING GOAL: CAPITAL PRESERVATION (target 2-4% annual, minimize losses). "
        "Preserve capital above all. Consider treasury ETFs and low-volatility stocks "
        "like SHV, BIL, XLU, USMV, PG, JNJ — verify current yields from market data. "
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
    positions: list[Position],
    cash_available: float,
    market_data: list[Quote],
    news: list[NewsItem],
    guardrails_config: dict,
    technicals_csv: str = "",
    sector_csv: str = "",
    earnings_csv: str = "",
) -> list[TradeDecision]:
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

    # Build prompt with CSV sections for token efficiency (56% fewer tokens than JSON)
    prompt_parts = [
        risk_instruction,
        goal_instruction,
        "",
        f"PORTFOLIO ({len(positions)} positions, ${cash_available:.0f} cash):",
        json.dumps(positions),
        "",
        f"GUARDRAILS: {json.dumps(safe_config)}",
    ]

    # Add technicals if available
    if technicals_csv:
        prompt_parts.append("")
        prompt_parts.append(technicals_csv)

    # Add sector rotation if available
    if sector_csv:
        prompt_parts.append("")
        prompt_parts.append(sector_csv)

    # Add earnings calendar if available
    if earnings_csv:
        prompt_parts.append("")
        prompt_parts.append(earnings_csv)

    # Add news
    if news:
        prompt_parts.append("")
        prompt_parts.append(f"NEWS ({len(news)} items):")
        prompt_parts.append(json.dumps(news[:5]))  # Top 5 news items

    # Timeline goal context
    target_amount = guardrails_config.get("target_amount")
    target_date = guardrails_config.get("target_date")
    if target_amount and target_date:
        prompt_parts.append("")
        prompt_parts.append(
            f"TIMELINE GOAL: Grow portfolio to ${target_amount:,.0f} by {target_date}. "
            f"Current portfolio: ${cash_available + sum(p.get('market_value', 0) for p in positions):,.0f}. "
            "Factor this timeline into your urgency and willingness to take positions. "
            "If behind schedule, be more aggressive about finding opportunities."
        )

    prompt_parts.append("")
    prompt_parts.append(
        "Analyze the portfolio, technicals, sector rotation, earnings calendar, and news. "
        "You may suggest UP TO 3 trades if you see multiple opportunities. "
        "For each trade, decide: buy, sell, or hold. "
        "If nothing looks good, return a single hold. "
        "IMPORTANT: If a held stock has earnings within 2 days, consider reducing exposure. "
        "If buying a stock with earnings within 2 days, factor in binary event risk. "
        f"Minimum confidence to trade: {guardrails_config.get('min_confidence', 0.6)}. "
        "NaN means insufficient history for that indicator. "
        "Respond with JSON array: [{action, ticker, quantity, reasoning, confidence}, ...] "
        "Even for a single decision, wrap it in an array."
    )

    user_prompt = "\n".join(prompt_parts)

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
        return [{
            "action": "hold",
            "ticker": "",
            "quantity": 0,
            "reasoning": "Claude API timed out — holding as a safety measure",
            "confidence": 0.0,
        }]

    response_text = message.content[0].text

    # Strip markdown code fences if Claude wraps JSON in ```json ... ```
    stripped = response_text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[-1]  # remove first line (```json)
        if stripped.endswith("```"):
            stripped = stripped[:-3].strip()
        response_text = stripped

    try:
        parsed = json.loads(response_text)
    except json.JSONDecodeError:
        return [{
            "action": "hold",
            "ticker": "",
            "quantity": 0,
            "reasoning": f"Failed to parse Claude response: {response_text[:200]}",
            "confidence": 0.0,
        }]

    # Normalize: accept both single object and array
    decisions = parsed if isinstance(parsed, list) else [parsed]

    return [
        {
            "action": d.get("action", "hold"),
            "ticker": d.get("ticker", ""),
            "quantity": d.get("quantity", 0),
            "reasoning": d.get("reasoning", ""),
            "confidence": d.get("confidence", 0.0),
        }
        for d in decisions
    ]
