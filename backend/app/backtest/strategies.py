"""Pluggable backtest strategies — replace Claude for historical simulation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from app.technical_analysis import _compute_indicators


@dataclass
class StrategySignal:
    action: str  # "buy", "sell", "hold"
    ticker: str
    confidence: float
    reason: str


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


class BaseStrategy(ABC):
    """All backtest strategies implement this interface."""

    name: str = "base"
    description: str = ""

    @abstractmethod
    def decide(
        self,
        current_date: date,
        indicators: dict[str, dict],
        state: SimulationState,
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


class SMACrossover(BaseStrategy):
    """Buy on golden cross (SMA50 > SMA200), sell on death cross."""

    name = "sma_crossover"
    description = "Buy when SMA50 crosses above SMA200, sell when it crosses below"

    def decide(self, current_date, indicators, state, bars, params):
        fast = params.get("fast_period", 50)
        slow = params.get("slow_period", 200)
        signals = []

        for ticker, df in bars.items():
            if len(df) < slow:
                continue

            sma_fast = df["close"].rolling(fast).mean()
            sma_slow = df["close"].rolling(slow).mean()

            if len(sma_fast) < 2:
                continue

            prev_fast = sma_fast.iloc[-2]
            prev_slow = sma_slow.iloc[-2]
            curr_fast = sma_fast.iloc[-1]
            curr_slow = sma_slow.iloc[-1]

            if pd.isna(prev_fast) or pd.isna(prev_slow):
                continue

            # Golden cross: fast crosses above slow
            if prev_fast <= prev_slow and curr_fast > curr_slow:
                if ticker not in state.positions:
                    signals.append(StrategySignal(
                        action="buy", ticker=ticker,
                        confidence=0.7,
                        reason=f"Golden cross: SMA{fast} crossed above SMA{slow}",
                    ))

            # Death cross: fast crosses below slow
            elif prev_fast >= prev_slow and curr_fast < curr_slow:
                if ticker in state.positions:
                    signals.append(StrategySignal(
                        action="sell", ticker=ticker,
                        confidence=0.7,
                        reason=f"Death cross: SMA{fast} crossed below SMA{slow}",
                    ))

        return signals

    @staticmethod
    def get_param_schema():
        return [
            {"key": "fast_period", "label": "Fast SMA Period", "type": "number", "default": 50},
            {"key": "slow_period", "label": "Slow SMA Period", "type": "number", "default": 200},
        ]


class RSIMeanReversion(BaseStrategy):
    """Buy when RSI oversold, sell when overbought."""

    name = "rsi_mean_reversion"
    description = "Buy when RSI drops below oversold threshold, sell when it rises above overbought"

    def decide(self, current_date, indicators, state, bars, params):
        oversold = params.get("oversold", 30)
        overbought = params.get("overbought", 70)
        signals = []

        for ticker, ind in indicators.items():
            rsi = ind.get("rsi14")
            if rsi is None:
                continue

            if rsi < oversold and ticker not in state.positions:
                signals.append(StrategySignal(
                    action="buy", ticker=ticker,
                    confidence=min(0.9, (oversold - rsi) / oversold + 0.5),
                    reason=f"RSI oversold at {rsi:.1f} (threshold: {oversold})",
                ))
            elif rsi > overbought and ticker in state.positions:
                signals.append(StrategySignal(
                    action="sell", ticker=ticker,
                    confidence=min(0.9, (rsi - overbought) / (100 - overbought) + 0.5),
                    reason=f"RSI overbought at {rsi:.1f} (threshold: {overbought})",
                ))

        return signals

    @staticmethod
    def get_param_schema():
        return [
            {"key": "oversold", "label": "Oversold Threshold", "type": "number", "default": 30},
            {"key": "overbought", "label": "Overbought Threshold", "type": "number", "default": 70},
        ]


class BuyAndHold(BaseStrategy):
    """Equal-weight buy-and-hold — baseline benchmark."""

    name = "buy_and_hold"
    description = "Buy equal weights on day 1 and hold — the benchmark to beat"

    def decide(self, current_date, indicators, state, bars, params):
        # Only buy on the first day (no existing positions)
        if state.positions:
            return []

        signals = []
        for ticker in bars:
            signals.append(StrategySignal(
                action="buy", ticker=ticker,
                confidence=1.0,
                reason="Buy-and-hold: initial equal-weight allocation",
            ))
        return signals

    @staticmethod
    def get_param_schema():
        return []


# Registry of all available strategies
STRATEGY_REGISTRY: dict[str, type[BaseStrategy]] = {
    "sma_crossover": SMACrossover,
    "rsi_mean_reversion": RSIMeanReversion,
    "buy_and_hold": BuyAndHold,
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
