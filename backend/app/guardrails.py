"""Risk-profile presets and trading-goal definitions.

Portfolio-only model: there is no global guardrails singleton. Every portfolio
carries its own strategy fields (risk_profile, trading_goal, trading_frequency,
cooldown_hours, min_confidence, kelly_fraction, circuit_breaker_*). This module
provides the preset table and the function the per-portfolio executor uses
to translate a profile string into the dict shape Claude's prompt builder
expects.

Removed in the consolidation:
- GuardrailsConfig / GuardrailsAudit DB models (see migration 076)
- load_guardrails / save_guardrails / check_guardrails — per-portfolio
  validation now lives inline in plans/executor.py
- GuardrailsUpdate Pydantic model — strategy updates flow through
  POST /portfolios/{id}/strategy
"""


# Risk profile presets — all values are percentages of portfolio or absolute limits
RISK_PRESETS = {
    "conservative": {
        "max_portfolio_pct": 0.30,
        "max_single_trade_pct": 0.05,
        "stop_loss_threshold": 0.03,
        "daily_order_limit": 3,
        "min_confidence": 0.75,
        "max_positions": 5,
    },
    "moderate": {
        "max_portfolio_pct": 0.60,
        "max_single_trade_pct": 0.10,
        "stop_loss_threshold": 0.05,
        "daily_order_limit": 5,
        "min_confidence": 0.60,
        "max_positions": 10,
    },
    "aggressive": {
        "max_portfolio_pct": 0.90,
        "max_single_trade_pct": 0.20,
        "stop_loss_threshold": 0.08,
        "daily_order_limit": 10,
        "min_confidence": 0.45,
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
