"""RSI Mean Reversion strategy."""

from __future__ import annotations

from app.strategies.base import BaseStrategy, StrategySignal


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
