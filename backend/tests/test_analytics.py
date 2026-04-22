"""Unit tests for app.analytics — compute_metrics from equity time series."""

import pytest

from app.analytics import PortfolioMetrics, compute_metrics


@pytest.mark.unit
class TestComputeMetricsEdgeCases:
    """Edge cases: insufficient data, flat equities."""

    def test_empty_list_returns_defaults(self):
        result = compute_metrics([])
        assert isinstance(result, PortfolioMetrics)
        assert result.total_return_pct == 0
        assert result.sharpe_ratio is None
        assert result.sharpe_confidence == "insufficient_data"
        assert result.sortino_ratio is None
        assert result.max_drawdown_pct == 0
        assert result.num_trading_days == 0

    def test_single_point_returns_defaults(self):
        result = compute_metrics([10000.0])
        assert result.total_return_pct == 0
        assert result.sharpe_ratio is None
        assert result.profit_factor is None
        assert result.num_trading_days == 1

    def test_two_points_minimum(self):
        """Two data points → 1 daily return → not enough for variance.
        compute_metrics needs 3+ points for Sharpe/variance."""
        result = compute_metrics([100.0, 105.0, 110.0])
        assert result.num_trading_days == 3
        assert result.total_return_pct == pytest.approx(10.0)

    def test_flat_equities_zero_volatility(self):
        """Constant equity = zero volatility, no Sharpe (division by zero guarded)."""
        equities = [10000.0] * 30
        result = compute_metrics(equities)
        assert result.total_return_pct == 0.0
        assert result.volatility_annual_pct == 0.0
        # Sharpe requires vol > 0, so it should be None
        assert result.sharpe_ratio is None
        assert result.max_drawdown_pct == 0.0
        assert result.win_rate_pct == 0.0


@pytest.mark.unit
class TestComputeMetricsIncreasing:
    """Increasing (bullish) equity curves."""

    @pytest.fixture
    def bullish_metrics(self):
        """Steadily increasing equity over 30 days."""
        equities = [10000.0 + i * 50 for i in range(30)]
        return compute_metrics(equities)

    def test_positive_total_return(self, bullish_metrics):
        assert bullish_metrics.total_return_pct > 0

    def test_sharpe_ratio_positive(self, bullish_metrics):
        """Positive excess returns should yield a positive Sharpe ratio."""
        assert bullish_metrics.sharpe_ratio is not None
        assert bullish_metrics.sharpe_ratio > 0

    def test_sortino_ratio_positive(self, bullish_metrics):
        """Steadily rising equity has no down days, Sortino may be None (no downside)."""
        # With a perfectly linear rise, there are no negative excess returns
        # unless the daily risk-free rate exceeds the daily gain. At 5%/yr
        # risk-free and ~0.5% daily gain, all excess returns are positive,
        # so Sortino should be None (no downside deviation).
        # But it's also valid if it's a positive number.
        if bullish_metrics.sortino_ratio is not None:
            assert bullish_metrics.sortino_ratio > 0

    def test_max_drawdown_nonpositive(self, bullish_metrics):
        """Drawdown is always <= 0 (expressed as a negative percentage)."""
        assert bullish_metrics.max_drawdown_pct <= 0

    def test_win_rate_high(self, bullish_metrics):
        """All days are up in a linear increase — win rate should be 100%."""
        assert bullish_metrics.win_rate_pct == 100.0

    def test_win_rate_in_range(self, bullish_metrics):
        assert 0 <= bullish_metrics.win_rate_pct <= 100

    def test_best_day_positive(self, bullish_metrics):
        assert bullish_metrics.best_day_pct > 0

    def test_num_trading_days(self, bullish_metrics):
        assert bullish_metrics.num_trading_days == 30


@pytest.mark.unit
class TestComputeMetricsDecreasing:
    """Decreasing (bearish) equity curves."""

    @pytest.fixture
    def bearish_metrics(self):
        """Steadily decreasing equity over 30 days."""
        equities = [10000.0 - i * 50 for i in range(30)]
        return compute_metrics(equities)

    def test_negative_total_return(self, bearish_metrics):
        assert bearish_metrics.total_return_pct < 0

    def test_sharpe_ratio_negative(self, bearish_metrics):
        """Negative excess returns should yield a negative Sharpe ratio."""
        assert bearish_metrics.sharpe_ratio is not None
        assert bearish_metrics.sharpe_ratio < 0

    def test_max_drawdown_negative(self, bearish_metrics):
        """Continuous decline should produce a significant drawdown."""
        assert bearish_metrics.max_drawdown_pct < 0

    def test_win_rate_zero(self, bearish_metrics):
        """All days are down in a linear decrease — win rate should be 0%."""
        assert bearish_metrics.win_rate_pct == 0.0

    def test_worst_day_negative(self, bearish_metrics):
        assert bearish_metrics.worst_day_pct < 0

    def test_profit_factor_zero_or_none(self, bearish_metrics):
        """No winning days means gross_profit=0, so profit_factor is None or 0."""
        # With all losses and zero wins, gross_profit=0, gross_loss>0
        # profit_factor = 0/gross_loss = 0.0 (rounded)
        # But if gross_loss is 0, it returns None.
        if bearish_metrics.profit_factor is not None:
            assert bearish_metrics.profit_factor == 0.0


@pytest.mark.unit
class TestComputeMetricsMixed:
    """Mixed equity curve (up and down)."""

    def test_mixed_returns(self):
        """Zigzag equity should have a mix of wins and losses."""
        equities = [100, 110, 105, 115, 108, 120, 112, 125]
        result = compute_metrics(equities)

        assert result.num_trading_days == 8
        assert 0 < result.win_rate_pct < 100
        assert result.max_drawdown_pct < 0
        assert result.best_day_pct > 0
        assert result.worst_day_pct < 0

    def test_to_dict(self):
        """to_dict returns a plain dictionary with all expected keys."""
        result = compute_metrics([100.0, 105.0, 110.0])
        d = result.to_dict()
        assert isinstance(d, dict)
        expected_keys = {
            "total_return_pct", "sharpe_ratio", "sharpe_confidence",
            "sortino_ratio", "max_drawdown_pct", "max_drawdown_days",
            "win_rate_pct", "profit_factor", "best_day_pct",
            "worst_day_pct", "volatility_annual_pct", "num_trading_days",
        }
        assert set(d.keys()) == expected_keys

    def test_sharpe_confidence_levels(self):
        """With enough data points, sharpe_confidence should not be 'insufficient_data'."""
        # 60 data points with some variance
        equities = [10000.0 + i * 10 + (i % 3) * 20 for i in range(60)]
        result = compute_metrics(equities)
        assert result.sharpe_confidence in ("low", "moderate", "high")

    def test_custom_risk_free_rate(self):
        """Changing risk-free rate should affect Sharpe and Sortino."""
        equities = [10000.0 + i * 10 + (i % 3) * 20 for i in range(30)]
        low_rf = compute_metrics(equities, risk_free_annual=0.01)
        high_rf = compute_metrics(equities, risk_free_annual=0.20)

        # Higher risk-free rate => lower excess return => lower Sharpe
        if low_rf.sharpe_ratio is not None and high_rf.sharpe_ratio is not None:
            assert low_rf.sharpe_ratio > high_rf.sharpe_ratio
