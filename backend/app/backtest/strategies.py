"""Backtest-specific state types + re-export shim for backward compatibility.

Strategy classes (BaseStrategy, StrategySignal, STRATEGY_REGISTRY, and all
concrete strategies) have moved to app.strategies.*. Prefer importing from
there. This module will be removed after one release.

PositionInfo and SimulationState moved to app.strategies.state (the live
executor uses them too); re-exported here for old imports.
"""

from __future__ import annotations


# Re-export everything that external code previously imported from here.
# New code should import directly from app.strategies.
from app.strategies import (  # noqa: F401
    PositionInfo,
    SimulationState,
    BaseStrategy,
    BuyAndHold,
    DualMomentum,
    RSIMeanReversion,
    SMACrossover,
    STRATEGY_REGISTRY,
    StrategySignal,
    get_strategy_info,
)
