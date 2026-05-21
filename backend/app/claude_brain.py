"""Claude Sonnet trading decision engine."""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING

import anthropic

from app.config import settings
from app.pipeline_types import Position, Quote, NewsItem, TradeDecision

if TYPE_CHECKING:
    from app.plans.models import Portfolio

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

# Broad ~100-name candidate universe for maximize_returns. Liquid US large-caps
# spanning all 11 GICS sectors + a few broad/sector ETFs, so Claude can hunt for
# setups beyond mega-cap tech instead of rotating the same handful of names.
# Constraints: no crypto (StockHistoricalDataClient returns wrong prices — see
# test_goal_prompts.py), no dotted/class-share tickers (e.g. BRK.B) that the
# Alpaca bar fetch chokes on. Edit this list to reshape the universe.
MAXIMIZE_RETURNS_UNIVERSE: list[str] = [
    # Information technology
    "AAPL", "MSFT", "NVDA", "AVGO", "ORCL", "CRM", "ADBE", "AMD", "CSCO",
    "ACN", "QCOM", "TXN", "IBM", "NOW", "INTU", "AMAT", "MU", "INTC",
    # Communication services
    "GOOGL", "META", "NFLX", "DIS", "CMCSA", "TMUS", "VZ", "T",
    # Consumer discretionary
    "AMZN", "TSLA", "HD", "MCD", "NKE", "LOW", "SBUX", "BKNG", "TJX",
    # Consumer staples
    "PG", "KO", "PEP", "COST", "WMT", "PM", "MO", "CL",
    # Health care
    "UNH", "JNJ", "LLY", "ABBV", "MRK", "PFE", "TMO", "ABT", "DHR",
    "BMY", "AMGN", "MDT",
    # Financials
    "JPM", "V", "MA", "BAC", "WFC", "GS", "MS", "AXP", "SPGI", "BLK",
    "C", "SCHW",
    # Industrials
    "CAT", "BA", "HON", "UPS", "GE", "RTX", "LMT", "DE", "UNP", "MMM",
    # Energy
    "XOM", "CVX", "COP", "SLB", "EOG",
    # Materials
    "LIN", "SHW", "FCX", "NEM",
    # Utilities
    "NEE", "DUK", "SO",
    # Real estate
    "AMT", "PLD", "EQIX",
    # Broad / sector ETFs
    "SPY", "QQQ", "IWM", "XLK", "XLF", "XLE", "XLV",
]

GOAL_WATCHLIST: dict[str, list[str]] = {
    "maximize_returns":      MAXIMIZE_RETURNS_UNIVERSE,
    "steady_income":         ["SCHD", "VYM", "JEPI", "O", "JNJ", "PG"],
    "capital_preservation":  ["SHV", "BIL", "XLU", "USMV", "PG", "JNJ"],
    "beat_sp500":            ["XLK", "XLV", "XLF", "XLE", "XLI", "XLY", "XLP", "XLB", "XLRE", "XLU"],
    "swing_trading":         ["AAPL", "MSFT", "NVDA", "TSLA", "GOOGL", "AMD", "QQQ"],
    "passive_index":         ["VOO", "VTI", "VXUS"],
}

GOAL_PROMPTS = {
    "maximize_returns": (
        "TRADING GOAL: MAXIMIZE RETURNS (target 15-30% annual). "
        "Seek highest risk-adjusted returns through momentum and factor investing. "
        "Evaluate the FULL candidate set in MARKET QUOTES and TECHNICALS — do NOT "
        "limit yourself to mega-cap tech. Hunt across every sector for the strongest "
        "setups, including names you do not currently hold. "
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
        "Focus on: AAPL, MSFT, NVDA, TSLA, GOOGL, AMD, QQQ. "
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


def _pct(val) -> float:
    """Convert a broker percent value (float, int, or '1.23%') to a plain float."""
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    return float(str(val).rstrip("%") or 0)


async def get_trade_decision(
    positions: list[Position],
    cash_available: float,
    market_data: list[Quote],
    news: list[NewsItem],
    guardrails_config: dict,
    technicals_csv: str = "",
    sector_csv: str = "",
    earnings_csv: str = "",
    total_invested: float = 0.0,
    orders_used_today: int = 0,
) -> list[TradeDecision]:
    """Send portfolio context to Claude and get a structured trade decision.

    `total_invested`, `orders_used_today`, and `len(positions)` let Claude
    compute headroom against guardrail limits BEFORE proposing a trade —
    closes the information-asymmetry that previously caused valid signals
    to be blocked at validation time.
    """
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

    # Compute headroom against binding guardrails so Claude can plan within them.
    # Without these, Claude sees only the limits — not how much of each is already used —
    # and ends up proposing trades that pass intent but fail validation.
    max_total_invested = float(safe_config.get("max_total_invested", 0) or 0)
    max_single_trade_size = float(safe_config.get("max_single_trade_size", 0) or 0)
    daily_order_limit = int(safe_config.get("daily_order_limit", 0) or 0)
    max_positions = int(safe_config.get("max_positions", 0) or 0)
    min_confidence = float(safe_config.get("min_confidence", 0.6) or 0.6)

    # Round to cents so float subtraction doesn't produce a phantom ~1e-10
    # of "headroom" when total_invested ≈ max_total_invested.
    invest_headroom = round(max(0.0, max_total_invested - total_invested), 2) if max_total_invested else 0.0
    orders_remaining = max(0, daily_order_limit - orders_used_today) if daily_order_limit else 0
    position_slots_open = max(0, max_positions - len(positions)) if max_positions else 0
    # Effective single-trade ceiling is whichever of (cash, max_single, invest_headroom) is smallest
    effective_buy_ceiling = cash_available
    if max_single_trade_size:
        effective_buy_ceiling = min(effective_buy_ceiling, max_single_trade_size)
    if max_total_invested:
        effective_buy_ceiling = min(effective_buy_ceiling, invest_headroom)

    # Build prompt with CSV sections for token efficiency (56% fewer tokens than JSON)
    prompt_parts = [
        risk_instruction,
        goal_instruction,
        "",
        f"PORTFOLIO ({len(positions)} positions, ${cash_available:.0f} cash):",
        json.dumps(positions),
    ]

    if market_data:
        prompt_parts += [
            "",
            f"MARKET QUOTES ({len(market_data)} stocks) — ticker,price,change_pct,volume:",
            "\n".join(
                f"{q['ticker']},{float(q['price']):.2f},{_pct(q.get('change_pct', 0)):+.2f}%,{q.get('volume', 0)}"
                for q in market_data
            ),
        ]

    prompt_parts += [
        "",
        f"GUARDRAILS: {json.dumps(safe_config)}",
        "",
        "USAGE / HEADROOM (you must size every proposal to fit these):",
        f"- Total invested: ${total_invested:,.0f} / ${max_total_invested:,.0f}  →  ${invest_headroom:,.0f} buy headroom",
        f"- Orders today:   {orders_used_today} / {daily_order_limit}  →  {orders_remaining} slots remaining",
        f"- Open positions: {len(positions)} / {max_positions}  →  {position_slots_open} slots open",
        f"- Max single buy this cycle: ${effective_buy_ceiling:,.0f}  (min of cash, max_single_trade, invest_headroom)",
        f"- Min confidence to clear validation: {min_confidence:.0%}",
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

    # Timeline goal context — both fields are coerced/validated before
    # interpolation as defense-in-depth against prompt injection. Pydantic
    # validators on GuardrailsUpdate already enforce shape at the route
    # boundary; this is the second line.
    target_amount_raw = guardrails_config.get("target_amount")
    target_date_raw = guardrails_config.get("target_date")
    target_amount: float | None = None
    target_date: str | None = None
    if target_amount_raw is not None:
        try:
            target_amount = float(target_amount_raw)
        except (TypeError, ValueError):
            target_amount = None
    if target_date_raw is not None and re.match(r"^\d{4}-\d{2}-\d{2}$", str(target_date_raw)):
        target_date = str(target_date_raw)
    if target_amount and target_amount > 0 and target_date:
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
        f"You may suggest UP TO {min(3, orders_remaining) if daily_order_limit else 3} trades. "
        "For each trade, decide: buy, sell, or hold. "
        "If nothing looks good, return a single hold. "
        "IMPORTANT: If a held stock has earnings within 2 days, consider reducing exposure. "
        "If buying a stock with earnings within 2 days, factor in binary event risk. "
        f"Minimum confidence to trade: {min_confidence}. "
        "NaN means insufficient history for that indicator. "
        "SIZING REQUIREMENT — every proposed buy MUST satisfy ALL of: "
        f"(price × qty) ≤ ${effective_buy_ceiling:,.0f}; "
        f"price × qty ≤ ${max_single_trade_size:,.0f} (max_single_trade_size); "
        f"running total of all your buys this cycle ≤ ${invest_headroom:,.0f} (invest_headroom); "
        f"confidence ≥ {min_confidence}. "
        f"Skip the trade if you can't fit it; do NOT propose oversized trades expecting validation to clamp them. "
        "FRACTIONAL SHARES are supported — use decimal qty (e.g., 0.5 of a $200 stock for $100). "
        "Sells are not gated by these dollar ceilings, only by holdings. "
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
    parsed = _parse_claude_json(response_text)

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


_REVIEW_SYSTEM_PROMPT = """You are a trading oversight reviewer. A deterministic rules-based strategy has produced a recommendation. Your job is NOT to second-guess the strategy on every call — your job is to flag situations where blindly following the rules would be clearly wrong. Override only with strong, specific justification.

Default to confirming the rules recommendation. Override is the exception, not the default. If you override, you must cite specific market data, earnings events, or news that the rules-based strategy could not see.

Override criteria (the only acceptable reasons to override):
- Earnings announcement within 2 days on a buy signal (binary event risk)
- A clear negative news catalyst for the specific stock (not general market fear)
- Portfolio kill switch is active

Respond with a JSON object only:
{"confirmed": true, "override_decision": null, "reasoning": "...", "override_confidence": 0.0}

If overriding, set confirmed=false and provide override_decision with {action, ticker, quantity, reasoning, confidence}.
You MUST respond with valid JSON only. No markdown, no explanation outside the JSON."""


async def review_trade_decision(
    rules_decision: dict,
    context: dict,
    portfolio: Portfolio,
) -> dict:
    """Ask Claude to confirm or override a single rules-based trade decision.

    Used by rules_with_claude_oversight mode. Fails closed: timeout or
    malformed response returns confirmed=True so oversight failures never
    block a valid strategy signal.

    Returns {confirmed, override_decision, reasoning, override_confidence}.
    """
    from app.strategies import STRATEGY_REGISTRY

    strategy_id = portfolio.strategy_id or "unknown"
    strategy_cls = STRATEGY_REGISTRY.get(strategy_id)
    strategy_description = (
        getattr(strategy_cls, "description", "No description available")
        if strategy_cls else "Unknown strategy"
    )

    # Whitelist expected keys to prevent prompt injection from strategy output
    _SAFE_DECISION_KEYS = {"action", "ticker", "quantity", "confidence", "reasoning"}
    safe_decision = {k: v for k, v in rules_decision.items() if k in _SAFE_DECISION_KEYS}

    _SAFE_CONTEXT_KEYS = {
        "cash_available", "positions", "quotes", "news",
        "technicals_csv", "earnings_csv", "sector_csv",
        "trading_goal", "risk_profile",
    }
    safe_context = {k: v for k, v in context.items() if k in _SAFE_CONTEXT_KEYS}

    prompt_parts = [
        f"Strategy: {strategy_id}",
        f"Description: {strategy_description}",
        "",
        "Rules-based recommendation:",
        json.dumps(safe_decision, indent=2),
        "",
        "Portfolio context:",
        f"- Trading goal: {portfolio.trading_goal}",
        f"- Risk profile: {portfolio.risk_profile}",
        f"- Cash available: ${safe_context.get('cash_available', 0):,.2f}",
    ]

    if context.get("kill_switch"):
        prompt_parts += ["", "KILL SWITCH: Active — no new buy or sell trades should be placed."]

    if safe_context.get("positions"):
        prompt_parts += ["", f"Positions: {json.dumps(safe_context['positions'])}"]

    if safe_context.get("technicals_csv"):
        prompt_parts += ["", safe_context["technicals_csv"]]

    if safe_context.get("earnings_csv"):
        prompt_parts += ["", safe_context["earnings_csv"]]

    if safe_context.get("sector_csv"):
        prompt_parts += ["", safe_context["sector_csv"]]

    if safe_context.get("news"):
        prompt_parts += ["", f"News ({len(safe_context['news'])} items):", json.dumps(safe_context["news"][:5])]

    if safe_context.get("quotes"):
        ticker = safe_decision.get("ticker", "")
        relevant = [q for q in safe_context["quotes"] if q.get("ticker") == ticker]
        if relevant:
            prompt_parts += ["", f"Quote for {ticker}: {json.dumps(relevant[0])}"]

    prompt_parts += [
        "",
        "Confirm or override. Default to confirmed=true unless you have strong, specific justification.",
    ]

    try:
        message = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=512,
            system=_REVIEW_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": "\n".join(prompt_parts)}],
            timeout=30.0,
        )
    except anthropic.APITimeoutError:
        logger.warning("Claude review API timed out — failing closed (confirmed=True)")
        return {
            "confirmed": True,
            "override_decision": None,
            "reasoning": "Review timed out — strategy signal confirmed by default",
            "override_confidence": 0.0,
        }

    parsed = _parse_claude_json(message.content[0].text)

    if not isinstance(parsed, dict) or "confirmed" not in parsed:
        logger.warning("Claude review returned malformed response — failing closed")
        return {
            "confirmed": True,
            "override_decision": None,
            "reasoning": "Malformed review response — strategy signal confirmed by default",
            "override_confidence": 0.0,
        }

    return {
        "confirmed": bool(parsed.get("confirmed", True)),
        "override_decision": parsed.get("override_decision"),
        "reasoning": str(parsed.get("reasoning", "")),
        "override_confidence": float(parsed.get("override_confidence", 0.0)),
    }


def _parse_claude_json(text: str) -> dict | list:
    """Robustly extract JSON from Claude's response, handling fences and extra text."""
    # 1. Try direct parse first (cleanest case)
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # 2. Strip markdown code fences (```json ... ``` or ``` ... ```)
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 3. Find the outermost JSON structure (array or object) anywhere in the text
    for start_char, end_char in [("[", "]"), ("{", "}")]:
        start = text.find(start_char)
        if start == -1:
            continue
        # Find matching closing bracket by counting nesting
        depth = 0
        for i in range(start, len(text)):
            if text[i] == start_char:
                depth += 1
            elif text[i] == end_char:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        break
        break

    # 4. All parsing failed — extract whatever reasoning we can
    logger.warning("Failed to parse Claude JSON, extracting text: %s", text[:300])
    # Try to find a reasoning-like sentence in the raw text
    reasoning = text.strip()
    # Remove any partial JSON artifacts for readability
    reasoning = re.sub(r'[{}\[\]"]+', "", reasoning)
    reasoning = re.sub(r"\s+", " ", reasoning).strip()
    if len(reasoning) > 500:
        reasoning = reasoning[:500] + "..."
    return {
        "action": "hold",
        "ticker": "",
        "quantity": 0,
        "reasoning": reasoning or "Claude returned an unparseable response",
        "confidence": 0.0,
    }
