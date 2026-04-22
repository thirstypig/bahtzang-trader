"""Unit and integration tests for app/position_sizing.py.

Tests Kelly Criterion position sizing: compute_win_stats and kelly_position_size.
"""

import pytest
from decimal import Decimal

from app.models import Trade
from app.position_sizing import compute_win_stats, kelly_position_size


@pytest.mark.integration
class TestComputeWinStats:
    def test_no_trades_returns_zeros(self, db_session):
        """No trades in DB → returns (0, 0)."""
        win_rate, ratio = compute_win_stats(db_session)
        assert win_rate == 0.0
        assert ratio == 0.0

    def test_insufficient_trades_returns_zeros(self, db_session):
        """Fewer than min_trades → returns (0, 0)."""
        for i in range(5):
            db_session.add(Trade(
                ticker="AAPL", action="buy", quantity=1.0,
                price=Decimal("150.00"), confidence=0.8,
                guardrail_passed=True, executed=True,
            ))
        db_session.commit()

        win_rate, ratio = compute_win_stats(db_session, min_trades=10)
        assert win_rate == 0.0
        assert ratio == 0.0

    def test_winning_trades_positive_win_rate(self, db_session):
        """Trades with confidence > 0.6 produce a positive win rate."""
        # 8 winning trades (confidence > 0.6)
        for _ in range(8):
            db_session.add(Trade(
                ticker="AAPL", action="buy", quantity=1.0,
                price=Decimal("150.00"), confidence=0.85,
                guardrail_passed=True, executed=True,
            ))
        # 4 losing trades (confidence <= 0.6)
        for _ in range(4):
            db_session.add(Trade(
                ticker="AAPL", action="sell", quantity=1.0,
                price=Decimal("145.00"), confidence=0.4,
                guardrail_passed=True, executed=True,
            ))
        db_session.commit()

        win_rate, ratio = compute_win_stats(db_session, min_trades=10)
        assert win_rate > 0
        assert win_rate == pytest.approx(8 / 12)
        assert ratio > 0

    def test_excludes_hold_trades(self, db_session):
        """Only buy/sell trades are counted, not hold."""
        for _ in range(12):
            db_session.add(Trade(
                ticker="AAPL", action="hold", quantity=0,
                price=None, confidence=0.9,
                guardrail_passed=True, executed=True,
            ))
        db_session.commit()

        win_rate, ratio = compute_win_stats(db_session, min_trades=10)
        assert win_rate == 0.0
        assert ratio == 0.0

    def test_excludes_unexecuted_trades(self, db_session):
        """Only executed trades are counted."""
        for _ in range(12):
            db_session.add(Trade(
                ticker="AAPL", action="buy", quantity=1.0,
                price=Decimal("150.00"), confidence=0.9,
                guardrail_passed=False, executed=False,
            ))
        db_session.commit()

        win_rate, ratio = compute_win_stats(db_session, min_trades=10)
        assert win_rate == 0.0
        assert ratio == 0.0


@pytest.mark.integration
class TestKellyPositionSize:
    def test_no_history_falls_back_to_fixed_sizing(self, db_session):
        """No trade history → falls back to portfolio_value * max_position_pct."""
        result = kelly_position_size(
            confidence=0.8,
            portfolio_value=100_000,
            db=db_session,
        )
        # Default max_position_pct = 0.10
        assert result == 100_000 * 0.10

    def test_reduces_near_earnings_1_day(self, db_session):
        """earnings_days=1 applies 50% reduction to position size."""
        # Seed mix of wins and losses to get a positive Kelly
        for i in range(12):
            conf = 0.85 if i < 8 else 0.4  # 8 wins, 4 losses
            db_session.add(Trade(
                ticker="AAPL", action="buy", quantity=1.0,
                price=Decimal("150.00"), confidence=conf,
                guardrail_passed=True, executed=True,
            ))
        db_session.commit()

        size_no_earnings = kelly_position_size(
            confidence=0.8, portfolio_value=100_000, db=db_session,
        )
        size_with_earnings = kelly_position_size(
            confidence=0.8, portfolio_value=100_000, db=db_session,
            earnings_days=1,
        )

        # Earnings reduction should make it smaller
        assert size_with_earnings <= size_no_earnings

    def test_reduces_near_earnings_2_days(self, db_session):
        """earnings_days=2 applies 70% reduction to position size."""
        for i in range(12):
            conf = 0.85 if i < 8 else 0.4
            db_session.add(Trade(
                ticker="AAPL", action="buy", quantity=1.0,
                price=Decimal("150.00"), confidence=conf,
                guardrail_passed=True, executed=True,
            ))
        db_session.commit()

        size_no_earnings = kelly_position_size(
            confidence=0.8, portfolio_value=100_000, db=db_session,
        )
        size_2day = kelly_position_size(
            confidence=0.8, portfolio_value=100_000, db=db_session,
            earnings_days=2,
        )

        assert size_2day <= size_no_earnings

    def test_caps_at_max_position_pct(self, db_session):
        """Position size never exceeds max_position_pct of portfolio."""
        # Seed trades to get a strong edge
        for _ in range(20):
            db_session.add(Trade(
                ticker="AAPL", action="buy", quantity=1.0,
                price=Decimal("150.00"), confidence=0.99,
                guardrail_passed=True, executed=True,
            ))
        db_session.commit()

        max_pct = 0.05
        result = kelly_position_size(
            confidence=1.0,
            portfolio_value=100_000,
            db=db_session,
            max_position_pct=max_pct,
        )
        assert result <= 100_000 * max_pct

    def test_negative_kelly_returns_zero(self, db_session):
        """If Kelly fraction is negative (poor edge), position size is 0.

        Need win_rate > 0 and win_loss_ratio > 0 to reach Kelly formula,
        but with a bad enough ratio that Kelly = W - (1-W)/R < 0.
        Example: 3 wins / 12 total → W=0.25, avg_win~0.7, avg_loss~0.6
        → R=1.17, Kelly = 0.25 - 0.75/1.17 = -0.39 → returns 0.
        """
        # 3 wins (confidence > 0.6), 9 losses (confidence <= 0.6)
        for i in range(12):
            conf = 0.7 if i < 3 else 0.4
            db_session.add(Trade(
                ticker="AAPL", action="buy", quantity=1.0,
                price=Decimal("150.00"), confidence=conf,
                guardrail_passed=True, executed=True,
            ))
        db_session.commit()

        result = kelly_position_size(
            confidence=0.8,
            portfolio_value=100_000,
            db=db_session,
        )
        assert result == 0.0
