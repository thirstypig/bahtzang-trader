"""Position/portfolio state handed to strategies' decide().

Shared infrastructure: the backtest engine simulates with it, and the live executor
builds one from virtual positions for rules-mode portfolios.
"""

from dataclasses import dataclass, field


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
