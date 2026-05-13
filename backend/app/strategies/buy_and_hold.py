"""Buy-and-hold benchmark strategy."""

from __future__ import annotations

from app.strategies.base import BaseStrategy, StrategySignal


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
