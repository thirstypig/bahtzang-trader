"""Screener ranking engine — pure-logic tests.

rank_universe is deterministic and IO-free, so we feed it synthetic price series
and assert the ranking behaves: trend/momentum wins, junk is filtered.
"""

import numpy as np
import pandas as pd
import pytest

from app.screener.engine import rank_universe, _compute_factors, MIN_BARS


def _bars(daily: float = 0.0, n: int = 260, noise: float = 0.0, seed: int = 0) -> pd.DataFrame:
    """Synthetic OHLCV: a price path with a daily drift and optional vol."""
    rng = np.random.default_rng(seed)
    rets = np.full(n, daily) + (rng.normal(0, noise, n) if noise else 0.0)
    closes = 100.0 * np.cumprod(1 + rets)
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    return pd.DataFrame(
        {"open": closes, "high": closes, "low": closes, "close": closes, "volume": 1_000_000},
        index=idx,
    )


@pytest.mark.unit
class TestRankUniverse:
    def test_uptrend_outranks_downtrend(self):
        bars = {
            "UP": _bars(daily=0.002),
            "DOWN": _bars(daily=-0.002),
            "SPY": _bars(daily=0.0003),
        }
        order = [r["ticker"] for r in rank_universe(bars, top_n=10)]
        assert "UP" in order and "DOWN" in order
        assert order.index("UP") < order.index("DOWN")

    def test_insufficient_history_is_excluded(self):
        bars = {
            "UP": _bars(daily=0.002),
            "SHORT": _bars(daily=0.002, n=MIN_BARS - 10),
            "SPY": _bars(daily=0.0003),
        }
        assert "SHORT" not in [r["ticker"] for r in rank_universe(bars)]

    def test_extreme_volatility_is_excluded(self):
        bars = {
            "CALM": _bars(daily=0.001, noise=0.005, seed=1),
            "WILD": _bars(daily=0.001, noise=0.12, seed=2),  # ~190% annualized vol
            "SPY": _bars(daily=0.0003),
        }
        ranked = [r["ticker"] for r in rank_universe(bars)]
        assert "WILD" not in ranked
        assert "CALM" in ranked

    def test_top_n_caps_and_numbers_ranks(self):
        bars = {f"T{i}": _bars(daily=0.0005 * (i + 1)) for i in range(10)}
        bars["SPY"] = _bars(daily=0.0003)
        ranked = rank_universe(bars, top_n=3)
        assert len(ranked) == 3
        assert [r["rank"] for r in ranked] == [1, 2, 3]

    def test_empty_universe_returns_empty(self):
        assert rank_universe({}, top_n=10) == []


@pytest.mark.unit
class TestComputeFactors:
    def test_returns_none_below_min_bars(self):
        assert _compute_factors(_bars(n=MIN_BARS - 1), None) is None

    def test_trend_score_high_for_strong_uptrend(self):
        f = _compute_factors(_bars(daily=0.002), None)
        assert f is not None
        assert f["trend_score"] == 1.0  # price > 50d SMA > 200d SMA
