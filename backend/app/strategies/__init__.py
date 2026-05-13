"""Shared trading strategy infrastructure.

Available to both the backtest engine and the live executor.
Import from here, not from app.backtest.strategies (feature isolation).

    from app.strategies import BaseStrategy, StrategySignal, STRATEGY_REGISTRY
    from app.strategies import DualMomentum, SMACrossover
"""

from app.strategies.base import BaseStrategy, StrategySignal
from app.strategies.buy_and_hold import BuyAndHold
from app.strategies.dual_momentum import DualMomentum
from app.strategies.registry import STRATEGY_REGISTRY, get_strategy_info
from app.strategies.rsi_mean_reversion import RSIMeanReversion
from app.strategies.sma_crossover import SMACrossover

__all__ = [
    "BaseStrategy",
    "StrategySignal",
    "STRATEGY_REGISTRY",
    "get_strategy_info",
    "SMACrossover",
    "RSIMeanReversion",
    "BuyAndHold",
    "DualMomentum",
]
