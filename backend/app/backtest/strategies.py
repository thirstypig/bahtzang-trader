"""Backtest-specific state types + re-export shim for backward compatibility.

Strategy classes (BaseStrategy, StrategySignal, STRATEGY_REGISTRY, and all
concrete strategies) have moved to app.strategies.*. Prefer importing from
there. This module will be removed after one release.

PositionInfo and SimulationState remain here — they are backtest-specific
(the live executor uses Alpaca positions, not SimulationState).
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Re-export everything that external code previously imported from here.
# New code should import directly from app.strategies.
from app.strategies import (  # noqa: F401
    BaseStrategy,
    BuyAndHold,
    DualMomentum,
    RSIMeanReversion,
    SMACrossover,
    STRATEGY_REGISTRY,
    StrategySignal,
    get_strategy_info,
)


@dataclass
class PositionInfo:
    quantity: int
    avg_price: float


@dataclass
class SimulationState:
    cash: float
    positions: dict[str, PositionInfo] = field(default_factory=dict)
    equity_curve: list[dict] = field(default_factory=list)
    trades: list[dict] = field(default_factory=list)
