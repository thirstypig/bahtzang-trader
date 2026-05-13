"""SMA Crossover strategy."""

from __future__ import annotations

import pandas as pd

from app.strategies.base import BaseStrategy, StrategySignal


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
