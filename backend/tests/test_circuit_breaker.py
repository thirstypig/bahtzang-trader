"""Tests for app/circuit_breaker.py — portfolio drawdown circuit breakers."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.circuit_breaker import (
    ORANGE,
    RED,
    YELLOW,
    _count_consecutive_losses,
    check_circuit_breakers,
)
from app.models import PortfolioSnapshot, Trade


DEFAULT_CONFIG = {
    "circuit_breaker_daily_pct": 0.05,
    "circuit_breaker_weekly_pct": 0.10,
}


# ---------------------------------------------------------------------------
# check_circuit_breakers
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestCheckCircuitBreakers:
    def test_no_snapshots_returns_none(self, db_session):
        """No portfolio snapshots → not enough data, pass through."""
        level, reason = check_circuit_breakers(db_session, 50000.0, DEFAULT_CONFIG)
        assert level is None
        assert reason is None

    def test_single_snapshot_returns_none(self, db_session):
        """Only one snapshot → < 2 required, pass through."""
        snap = PortfolioSnapshot(
            date=date.today(),
            total_equity=Decimal("50000"),
            cash=Decimal("10000"),
            invested=Decimal("40000"),
            unrealized_pnl=Decimal("0"),
        )
        db_session.add(snap)
        db_session.commit()

        level, reason = check_circuit_breakers(db_session, 50000.0, DEFAULT_CONFIG)
        assert level is None
        assert reason is None

    def test_normal_day_returns_none(self, db_session):
        """Portfolio unchanged → no breakers triggered."""
        today = date.today()
        snaps = [
            PortfolioSnapshot(
                date=today - timedelta(days=3),
                total_equity=Decimal("50000"),
                cash=Decimal("10000"),
                invested=Decimal("40000"),
                unrealized_pnl=Decimal("0"),
            ),
            PortfolioSnapshot(
                date=today - timedelta(days=1),
                total_equity=Decimal("50000"),
                cash=Decimal("10000"),
                invested=Decimal("40000"),
                unrealized_pnl=Decimal("0"),
            ),
        ]
        db_session.add_all(snaps)
        db_session.commit()

        level, reason = check_circuit_breakers(db_session, 50000.0, DEFAULT_CONFIG)
        assert level is None
        assert reason is None

    def test_daily_loss_triggers_red(self, db_session):
        """Daily loss > 5% → RED full halt."""
        today = date.today()
        snaps = [
            PortfolioSnapshot(
                date=today - timedelta(days=3),
                total_equity=Decimal("50000"),
                cash=Decimal("10000"),
                invested=Decimal("40000"),
                unrealized_pnl=Decimal("0"),
            ),
            PortfolioSnapshot(
                date=today - timedelta(days=1),
                total_equity=Decimal("50000"),
                cash=Decimal("10000"),
                invested=Decimal("40000"),
                unrealized_pnl=Decimal("0"),
            ),
        ]
        db_session.add_all(snaps)
        db_session.commit()

        # Current portfolio value dropped 6% from yesterday's $50k
        current_value = 47000.0  # -6%
        level, reason = check_circuit_breakers(db_session, current_value, DEFAULT_CONFIG)
        assert level == RED
        assert "Daily loss" in reason

    def test_weekly_loss_triggers_red(self, db_session):
        """Weekly loss > 10% → RED full halt."""
        today = date.today()
        snaps = [
            PortfolioSnapshot(
                date=today - timedelta(days=6),
                total_equity=Decimal("50000"),
                cash=Decimal("10000"),
                invested=Decimal("40000"),
                unrealized_pnl=Decimal("0"),
            ),
            # Yesterday equity already dropped a bit but not enough for daily RED
            PortfolioSnapshot(
                date=today - timedelta(days=1),
                total_equity=Decimal("45500"),
                cash=Decimal("10000"),
                invested=Decimal("35500"),
                unrealized_pnl=Decimal("-4500"),
            ),
        ]
        db_session.add_all(snaps)
        db_session.commit()

        # Current value is 44000 (12% below week start of 50000)
        # Daily: (44000 - 45500) / 45500 = -3.3% (below 5% daily RED)
        # Weekly: (44000 - 50000) / 50000 = -12% (above 10% weekly RED)
        level, reason = check_circuit_breakers(db_session, 44000.0, DEFAULT_CONFIG)
        assert level == RED
        assert "Weekly loss" in reason

    def test_daily_loss_triggers_yellow(self, db_session):
        """Daily loss > 3% (60% of 5%) but < 5% → YELLOW reduce position sizes."""
        today = date.today()
        snaps = [
            PortfolioSnapshot(
                date=today - timedelta(days=3),
                total_equity=Decimal("50000"),
                cash=Decimal("10000"),
                invested=Decimal("40000"),
                unrealized_pnl=Decimal("0"),
            ),
            PortfolioSnapshot(
                date=today - timedelta(days=1),
                total_equity=Decimal("50000"),
                cash=Decimal("10000"),
                invested=Decimal("40000"),
                unrealized_pnl=Decimal("0"),
            ),
        ]
        db_session.add_all(snaps)
        db_session.commit()

        # 3.5% daily loss: (48250 - 50000) / 50000 = -3.5%
        # Not enough for RED (5%) or ORANGE weekly check
        # Weekly: also -3.5% which is below 7% ORANGE threshold
        level, reason = check_circuit_breakers(db_session, 48250.0, DEFAULT_CONFIG)
        assert level == YELLOW
        assert "reducing position sizes" in reason

    def test_weekly_moderate_loss_triggers_orange(self, db_session):
        """Weekly loss > 7% (70% of 10%) but daily within bounds → ORANGE."""
        today = date.today()
        snaps = [
            PortfolioSnapshot(
                date=today - timedelta(days=6),
                total_equity=Decimal("50000"),
                cash=Decimal("10000"),
                invested=Decimal("40000"),
                unrealized_pnl=Decimal("0"),
            ),
            # Yesterday equity already lower (gradual weekly decline)
            PortfolioSnapshot(
                date=today - timedelta(days=1),
                total_equity=Decimal("46500"),
                cash=Decimal("10000"),
                invested=Decimal("36500"),
                unrealized_pnl=Decimal("-3500"),
            ),
        ]
        db_session.add_all(snaps)
        db_session.commit()

        # Current value: 46000
        # Daily: (46000 - 46500) / 46500 = -1.1% (no daily trigger)
        # Weekly: (46000 - 50000) / 50000 = -8% > 7% ORANGE threshold
        level, reason = check_circuit_breakers(db_session, 46000.0, DEFAULT_CONFIG)
        assert level == ORANGE
        assert "buys halted" in reason

    def test_small_gain_returns_none(self, db_session):
        """Portfolio gained value → no breakers."""
        today = date.today()
        snaps = [
            PortfolioSnapshot(
                date=today - timedelta(days=3),
                total_equity=Decimal("50000"),
                cash=Decimal("10000"),
                invested=Decimal("40000"),
                unrealized_pnl=Decimal("0"),
            ),
            PortfolioSnapshot(
                date=today - timedelta(days=1),
                total_equity=Decimal("50500"),
                cash=Decimal("10000"),
                invested=Decimal("40500"),
                unrealized_pnl=Decimal("500"),
            ),
        ]
        db_session.add_all(snaps)
        db_session.commit()

        level, reason = check_circuit_breakers(db_session, 51000.0, DEFAULT_CONFIG)
        assert level is None
        assert reason is None


# ---------------------------------------------------------------------------
# _count_consecutive_losses
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestCountConsecutiveLosses:
    def test_no_trades_returns_zero(self, db_session):
        assert _count_consecutive_losses(db_session) == 0

    def test_consecutive_low_confidence_sells(self, db_session):
        """Sells with confidence < 0.5 count as consecutive losses."""
        now = datetime.now(timezone.utc)
        for i in range(3):
            trade = Trade(
                ticker="AAPL",
                action="sell",
                quantity=1,
                price=Decimal("100.00"),
                confidence=0.3,
                guardrail_passed=True,
                executed=True,
                timestamp=now - timedelta(hours=i + 1),
            )
            db_session.add(trade)
        db_session.commit()

        assert _count_consecutive_losses(db_session) == 3

    def test_streak_broken_by_high_confidence_sell(self, db_session):
        """A sell with confidence >= 0.5 breaks the streak."""
        now = datetime.now(timezone.utc)

        # Most recent: low confidence (loss)
        t1 = Trade(
            ticker="AAPL",
            action="sell",
            quantity=1,
            price=Decimal("100.00"),
            confidence=0.3,
            guardrail_passed=True,
            executed=True,
            timestamp=now - timedelta(hours=1),
        )
        # Second: high confidence (not a loss) → breaks streak
        t2 = Trade(
            ticker="GOOG",
            action="sell",
            quantity=1,
            price=Decimal("200.00"),
            confidence=0.7,
            guardrail_passed=True,
            executed=True,
            timestamp=now - timedelta(hours=2),
        )
        # Third: low confidence (would be a loss, but streak already broken)
        t3 = Trade(
            ticker="MSFT",
            action="sell",
            quantity=1,
            price=Decimal("150.00"),
            confidence=0.2,
            guardrail_passed=True,
            executed=True,
            timestamp=now - timedelta(hours=3),
        )
        db_session.add_all([t1, t2, t3])
        db_session.commit()

        assert _count_consecutive_losses(db_session) == 1

    def test_streak_broken_by_buy(self, db_session):
        """A buy trade breaks the consecutive loss streak."""
        now = datetime.now(timezone.utc)

        sell = Trade(
            ticker="AAPL",
            action="sell",
            quantity=1,
            price=Decimal("100.00"),
            confidence=0.3,
            guardrail_passed=True,
            executed=True,
            timestamp=now - timedelta(hours=1),
        )
        buy = Trade(
            ticker="AAPL",
            action="buy",
            quantity=1,
            price=Decimal("95.00"),
            confidence=0.8,
            guardrail_passed=True,
            executed=True,
            timestamp=now - timedelta(hours=2),
        )
        db_session.add_all([sell, buy])
        db_session.commit()

        # Buy breaks the streak: only 1 consecutive loss
        assert _count_consecutive_losses(db_session) == 1

    def test_five_consecutive_losses_triggers_red(self, db_session):
        """5+ consecutive losses → RED via circuit breaker check."""
        now = datetime.now(timezone.utc)
        today = date.today()

        # Need 2 snapshots so circuit breaker doesn't exit early
        snaps = [
            PortfolioSnapshot(
                date=today - timedelta(days=3),
                total_equity=Decimal("50000"),
                cash=Decimal("10000"),
                invested=Decimal("40000"),
                unrealized_pnl=Decimal("0"),
            ),
            PortfolioSnapshot(
                date=today - timedelta(days=1),
                total_equity=Decimal("50000"),
                cash=Decimal("10000"),
                invested=Decimal("40000"),
                unrealized_pnl=Decimal("0"),
            ),
        ]
        db_session.add_all(snaps)

        # 5 consecutive low-confidence sells
        for i in range(5):
            trade = Trade(
                ticker="AAPL",
                action="sell",
                quantity=1,
                price=Decimal("100.00"),
                confidence=0.2,
                guardrail_passed=True,
                executed=True,
                timestamp=now - timedelta(hours=i + 1),
            )
            db_session.add(trade)
        db_session.commit()

        level, reason = check_circuit_breakers(db_session, 50000.0, DEFAULT_CONFIG)
        assert level == RED
        assert "consecutive losing trades" in reason

    def test_three_consecutive_losses_triggers_orange(self, db_session):
        """3 consecutive losses → ORANGE via circuit breaker check."""
        now = datetime.now(timezone.utc)
        today = date.today()

        snaps = [
            PortfolioSnapshot(
                date=today - timedelta(days=3),
                total_equity=Decimal("50000"),
                cash=Decimal("10000"),
                invested=Decimal("40000"),
                unrealized_pnl=Decimal("0"),
            ),
            PortfolioSnapshot(
                date=today - timedelta(days=1),
                total_equity=Decimal("50000"),
                cash=Decimal("10000"),
                invested=Decimal("40000"),
                unrealized_pnl=Decimal("0"),
            ),
        ]
        db_session.add_all(snaps)

        # 3 consecutive low-confidence sells
        for i in range(3):
            trade = Trade(
                ticker="AAPL",
                action="sell",
                quantity=1,
                price=Decimal("100.00"),
                confidence=0.2,
                guardrail_passed=True,
                executed=True,
                timestamp=now - timedelta(hours=i + 1),
            )
            db_session.add(trade)
        db_session.commit()

        level, reason = check_circuit_breakers(db_session, 50000.0, DEFAULT_CONFIG)
        assert level == ORANGE
        assert "consecutive losing trades" in reason
