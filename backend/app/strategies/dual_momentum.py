"""Gary Antonacci's Dual Momentum strategy."""

from __future__ import annotations

from datetime import date

import pandas as pd

from app.strategies.base import BaseStrategy, StrategySignal


class DualMomentum(BaseStrategy):
    """Gary Antonacci's Dual Momentum — monthly rotation across US equity, international equity, and bonds.

    Each month-end: pick SPY vs VEU by trailing 12-month return (relative momentum),
    then apply an absolute momentum gate vs BIL — rotate to bonds when equities trend negative.
    """

    name = "dual_momentum"
    description = (
        "Monthly rebalance: relative momentum picks SPY vs VEU, "
        "absolute momentum gate vs BIL rotates to bonds when equity trend is negative"
    )

    def decide(self, current_date, indicators, state, bars, params):
        lookback_months = int(params.get("lookback_months", 12))
        us_ticker = str(params.get("us_ticker", "SPY"))
        intl_ticker = str(params.get("intl_ticker", "VEU"))
        defensive_ticker = str(params.get("defensive_ticker", "BIL"))
        universe = [us_ticker, intl_ticker, defensive_ticker]

        if not self._is_month_end(current_date, bars):
            return []

        if not all(t in bars for t in universe):
            return []

        # Warm-up: require lookback_months of history for all tickers
        target_ts = pd.Timestamp(current_date) - pd.DateOffset(months=lookback_months)
        for ticker in universe:
            df = bars[ticker]
            if df.empty or df.index[0] > target_ts:
                return []

        def trailing_return(ticker: str) -> float:
            df = bars[ticker]
            close_today = float(df.iloc[-1]["close"])
            hist = df.loc[:target_ts]
            if hist.empty:
                return float("-inf")
            close_past = float(hist.iloc[-1]["close"])
            return (close_today / close_past) - 1.0

        us_ret = trailing_return(us_ticker)
        intl_ret = trailing_return(intl_ticker)
        bil_ret = trailing_return(defensive_ticker)

        # Relative momentum: pick the equity winner
        equity_winner = us_ticker if us_ret >= intl_ret else intl_ticker
        equity_winner_ret = us_ret if equity_winner == us_ticker else intl_ret
        equity_loser = intl_ticker if equity_winner == us_ticker else us_ticker
        equity_loser_ret = intl_ret if equity_winner == us_ticker else us_ret

        # Absolute momentum: if winner beats BIL, hold equity; else go defensive
        target = equity_winner if equity_winner_ret > bil_ret else defensive_ticker

        if set(state.positions.keys()) == {target}:
            return []

        signals: list[StrategySignal] = []

        for held in list(state.positions.keys()):
            signals.append(StrategySignal(
                action="sell",
                ticker=held,
                confidence=1.0,
                reason=f"DualMomentum rebalance: rotating out of {held} → {target}",
            ))

        if target == defensive_ticker:
            reason = (
                f"Absolute momentum: {equity_winner} {equity_winner_ret * 100:.1f}% "
                f"≤ BIL {bil_ret * 100:.1f}% — defensive rotation"
            )
        else:
            reason = (
                f"Relative: {equity_winner} {equity_winner_ret * 100:.1f}% > "
                f"{equity_loser} {equity_loser_ret * 100:.1f}%; "
                f"Absolute: {equity_winner_ret * 100:.1f}% > BIL {bil_ret * 100:.1f}%"
            )

        signals.append(StrategySignal(
            action="buy",
            ticker=target,
            confidence=1.0,
            reason=reason,
        ))

        return signals

    def _is_month_end(self, current_date: date, bars: dict[str, pd.DataFrame]) -> bool:
        """True if current_date is the last trading day of its calendar month."""
        all_dates: set[date] = set()
        for df in bars.values():
            all_dates.update(
                d.date() if hasattr(d, "date") else d for d in df.index
            )
        trading_days = sorted(all_dates)

        if current_date not in trading_days:
            return False

        idx = trading_days.index(current_date)
        if idx + 1 < len(trading_days):
            # A known future trading day exists — compare months directly
            return trading_days[idx + 1].month != current_date.month

        # current_date is the last known date (always the case with bars_so_far);
        # approximate by checking if the next business day is in a different month
        next_bday = (pd.Timestamp(current_date) + pd.offsets.BusinessDay(1)).date()
        return next_bday.month != current_date.month

    @staticmethod
    def get_param_schema() -> list[dict]:
        return [
            {"key": "lookback_months", "label": "Lookback (months)", "type": "number", "default": 12},
            {"key": "rebalance_frequency", "label": "Rebalance Frequency", "type": "string", "default": "monthly"},
            {"key": "us_ticker", "label": "US Equity ETF", "type": "string", "default": "SPY"},
            {"key": "intl_ticker", "label": "International ETF", "type": "string", "default": "VEU"},
            {"key": "defensive_ticker", "label": "Defensive ETF", "type": "string", "default": "BIL"},
        ]
