"""Strategy registry — single source of truth for all available strategies."""

from __future__ import annotations

from app.strategies.base import BaseStrategy
from app.strategies.buy_and_hold import BuyAndHold
from app.strategies.dual_momentum import DualMomentum
from app.strategies.rsi_mean_reversion import RSIMeanReversion
from app.strategies.sma_crossover import SMACrossover

STRATEGY_REGISTRY: dict[str, type[BaseStrategy]] = {
    "sma_crossover": SMACrossover,
    "rsi_mean_reversion": RSIMeanReversion,
    "buy_and_hold": BuyAndHold,
    "dual_momentum": DualMomentum,
}


def get_strategy_info() -> list[dict]:
    """Return strategy metadata for the frontend."""
    return [
        {
            "id": key,
            "name": cls.name.replace("_", " ").title(),
            "description": cls.description,
            "params": cls.get_param_schema(),
        }
        for key, cls in STRATEGY_REGISTRY.items()
    ]
