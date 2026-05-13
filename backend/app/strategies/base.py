"""Shared strategy abstractions — available to backtest engine and live executor."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd


@dataclass
class StrategySignal:
    action: str  # "buy", "sell", "hold"
    ticker: str
    confidence: float
    reason: str


class BaseStrategy(ABC):
    """All trading strategies implement this interface.

    Used by both the backtest engine (with SimulationState) and, in future,
    the live executor (with Alpaca positions). The `state` parameter is typed
    `Any` so the base class carries no dependency on backtest-specific types.
    """

    name: str = "base"
    description: str = ""

    @abstractmethod
    def decide(
        self,
        current_date: date,
        indicators: dict[str, dict],
        state: Any,
        bars: dict[str, pd.DataFrame],
        params: dict,
    ) -> list[StrategySignal]:
        """Return trading signals for the current day.

        May return multiple signals (e.g., sell one, buy another).
        """

    @staticmethod
    def get_param_schema() -> list[dict]:
        """Return parameter schema for the frontend form."""
        return []
