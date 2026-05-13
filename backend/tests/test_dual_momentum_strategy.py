"""Tests for DualMomentum strategy (Gary Antonacci).

Covers:
- 12-month warm-up gate
- Month-end rebalance detection (both positive and negative)
- Relative momentum winner selection (SPY vs VEU)
- Absolute momentum gate to BIL when equity trend is negative
- No-churn: same target as current position = no signals
- STRATEGY_REGISTRY + /backtest/strategies endpoint presence
"""

from datetime import date

import pandas as pd
import pytest

from app.backtest.strategies import (
    STRATEGY_REGISTRY,
    DualMomentum,
    PositionInfo,
    SimulationState,
)

TICKERS = ["SPY", "VEU", "BIL"]

DEFAULT_PARAMS = {
    "lookback_months": 12,
    "rebalance_frequency": "monthly",
    "us_ticker": "SPY",
    "intl_ticker": "VEU",
    "defensive_ticker": "BIL",
}


def _make_bars(
    start: str,
    end: str,
    prices: dict[str, tuple[float, float]],
) -> dict[str, pd.DataFrame]:
    """Synthetic bars with linearly interpolated close prices.

    prices: {ticker: (price_at_start, price_at_end)}
    The trailing-return calculation sees price_at_start at ~lookback boundary
    and price_at_end at current_date.
    """
    dates = pd.bdate_range(start=start, end=end)
    result: dict[str, pd.DataFrame] = {}
    for ticker, (p_start, p_end) in prices.items():
        n = len(dates)
        closes = (
            [p_start]
            if n == 1
            else [p_start + (p_end - p_start) * i / (n - 1) for i in range(n)]
        )
        result[ticker] = pd.DataFrame({"close": closes}, index=dates)
    return result


def _slice_to(bars: dict[str, pd.DataFrame], current_date: date) -> dict[str, pd.DataFrame]:
    """Simulate what the backtest engine does: slice bars to current_date."""
    ts = pd.Timestamp(current_date)
    return {t: df[df.index <= ts] for t, df in bars.items() if not df[df.index <= ts].empty}


@pytest.fixture
def strategy() -> DualMomentum:
    return DualMomentum()


@pytest.fixture
def empty_state() -> SimulationState:
    return SimulationState(cash=100_000.0)


# ---------------------------------------------------------------------------
# 1. Warm-up gate
# ---------------------------------------------------------------------------

class TestWarmup:
    def test_returns_empty_before_12_months(self, strategy, empty_state):
        """Strategy must return [] when bars span < lookback_months."""
        # Bars span only 11 months (Feb 2023 → Dec 2023)
        bars = _make_bars(
            "2023-02-01", "2023-12-29",
            {t: (100.0, 105.0) for t in TICKERS},
        )
        # Dec 29, 2023 is the last business day of December — a valid month-end
        current_date = date(2023, 12, 29)
        sliced = _slice_to(bars, current_date)
        signals = strategy.decide(current_date, {}, empty_state, sliced, DEFAULT_PARAMS)
        assert signals == []


# ---------------------------------------------------------------------------
# 2. Rebalance day detection
# ---------------------------------------------------------------------------

class TestRebalanceDayDetection:
    """Month-end triggers rebalance; mid-month does not."""

    def _bars_14mo(self) -> dict[str, pd.DataFrame]:
        """14 months of data — safely past the 12-month warm-up."""
        return _make_bars(
            "2022-11-01", "2024-01-31",
            {"SPY": (100.0, 115.0), "VEU": (100.0, 105.0), "BIL": (100.0, 102.0)},
        )

    def test_signals_emitted_on_month_end(self, strategy, empty_state):
        """Jan 31 (last business day of January 2024) → signals emitted."""
        bars = self._bars_14mo()
        current_date = date(2024, 1, 31)  # Wednesday — last bday of Jan 2024
        sliced = _slice_to(bars, current_date)
        signals = strategy.decide(current_date, {}, empty_state, sliced, DEFAULT_PARAMS)
        assert len(signals) > 0

    def test_no_signals_mid_month(self, strategy, empty_state):
        """Jan 16 (mid-month Wednesday) → no signals."""
        bars = self._bars_14mo()
        current_date = date(2024, 1, 16)
        sliced = _slice_to(bars, current_date)
        signals = strategy.decide(current_date, {}, empty_state, sliced, DEFAULT_PARAMS)
        assert signals == []


# ---------------------------------------------------------------------------
# 3. Relative momentum
# ---------------------------------------------------------------------------

class TestRelativeMomentum:
    def test_spy_wins_when_spy_outperforms_veu(self, strategy, empty_state):
        """SPY +20% vs VEU +5% → buy signal targets SPY."""
        bars = _make_bars(
            "2022-11-01", "2024-01-31",
            {"SPY": (100.0, 120.0), "VEU": (100.0, 105.0), "BIL": (100.0, 102.0)},
        )
        current_date = date(2024, 1, 31)
        sliced = _slice_to(bars, current_date)
        signals = strategy.decide(current_date, {}, empty_state, sliced, DEFAULT_PARAMS)
        buys = [s for s in signals if s.action == "buy"]
        assert len(buys) == 1
        assert buys[0].ticker == "SPY"

    def test_veu_wins_when_veu_outperforms_spy(self, strategy, empty_state):
        """VEU +25% vs SPY +8% → buy signal targets VEU."""
        bars = _make_bars(
            "2022-11-01", "2024-01-31",
            {"SPY": (100.0, 108.0), "VEU": (100.0, 125.0), "BIL": (100.0, 102.0)},
        )
        current_date = date(2024, 1, 31)
        sliced = _slice_to(bars, current_date)
        signals = strategy.decide(current_date, {}, empty_state, sliced, DEFAULT_PARAMS)
        buys = [s for s in signals if s.action == "buy"]
        assert len(buys) == 1
        assert buys[0].ticker == "VEU"


# ---------------------------------------------------------------------------
# 4. Absolute momentum gate → BIL
# ---------------------------------------------------------------------------

class TestAbsoluteMomentum:
    def test_rotates_to_bil_when_equity_winner_trails_bil(self, strategy, empty_state):
        """SPY -15% and VEU -25% — equity is negative; BIL +3% → rotate to BIL."""
        bars = _make_bars(
            "2022-11-01", "2024-01-31",
            {"SPY": (100.0, 85.0), "VEU": (100.0, 75.0), "BIL": (100.0, 103.0)},
        )
        current_date = date(2024, 1, 31)
        sliced = _slice_to(bars, current_date)
        signals = strategy.decide(current_date, {}, empty_state, sliced, DEFAULT_PARAMS)
        buys = [s for s in signals if s.action == "buy"]
        assert len(buys) == 1
        assert buys[0].ticker == "BIL"

    def test_confidence_is_1_for_defensive_signal(self, strategy, empty_state):
        """Rules-based strategy always emits confidence=1.0."""
        bars = _make_bars(
            "2022-11-01", "2024-01-31",
            {"SPY": (100.0, 85.0), "VEU": (100.0, 75.0), "BIL": (100.0, 103.0)},
        )
        current_date = date(2024, 1, 31)
        sliced = _slice_to(bars, current_date)
        signals = strategy.decide(current_date, {}, empty_state, sliced, DEFAULT_PARAMS)
        assert all(s.confidence == 1.0 for s in signals)


# ---------------------------------------------------------------------------
# 5. No-churn: same target = no signals
# ---------------------------------------------------------------------------

class TestNoChurn:
    def test_no_signals_when_already_in_target(self, strategy):
        """No rotation emitted when current position already matches the target."""
        # SPY +20% wins both relative and absolute momentum → target = SPY
        bars = _make_bars(
            "2022-11-01", "2024-01-31",
            {"SPY": (100.0, 120.0), "VEU": (100.0, 105.0), "BIL": (100.0, 102.0)},
        )
        current_date = date(2024, 1, 31)
        sliced = _slice_to(bars, current_date)

        state = SimulationState(
            cash=50_000.0,
            positions={"SPY": PositionInfo(quantity=100, avg_price=100.0)},
        )
        signals = strategy.decide(current_date, {}, state, sliced, DEFAULT_PARAMS)
        assert signals == []

    def test_rotation_emits_sell_and_buy_when_target_changes(self, strategy):
        """When the target changes, a sell + buy pair is emitted."""
        # SPY dominates → target = SPY
        bars = _make_bars(
            "2022-11-01", "2024-01-31",
            {"SPY": (100.0, 120.0), "VEU": (100.0, 105.0), "BIL": (100.0, 102.0)},
        )
        current_date = date(2024, 1, 31)
        sliced = _slice_to(bars, current_date)

        # But we currently hold BIL — a rotation is needed
        state = SimulationState(
            cash=50_000.0,
            positions={"BIL": PositionInfo(quantity=500, avg_price=92.0)},
        )
        signals = strategy.decide(current_date, {}, state, sliced, DEFAULT_PARAMS)
        actions = {s.action for s in signals}
        assert "sell" in actions
        assert "buy" in actions
        sell_tickers = {s.ticker for s in signals if s.action == "sell"}
        buy_tickers = {s.ticker for s in signals if s.action == "buy"}
        assert sell_tickers == {"BIL"}
        assert buy_tickers == {"SPY"}


# ---------------------------------------------------------------------------
# 6. Registry + endpoint presence
# ---------------------------------------------------------------------------

class TestRegistry:
    def test_dual_momentum_in_strategy_registry(self):
        assert "dual_momentum" in STRATEGY_REGISTRY
        assert STRATEGY_REGISTRY["dual_momentum"] is DualMomentum

    @pytest.mark.integration
    def test_dual_momentum_in_strategies_endpoint(self, client):
        resp = client.get("/backtest/strategies")
        assert resp.status_code == 200
        ids = {s["id"] for s in resp.json()}
        assert "dual_momentum" in ids

    def test_param_schema_has_required_keys(self):
        schema = DualMomentum.get_param_schema()
        keys = {p["key"] for p in schema}
        assert "lookback_months" in keys
        assert "rebalance_frequency" in keys
        assert "us_ticker" in keys
        assert "intl_ticker" in keys
        assert "defensive_ticker" in keys
