"""Tests for app/compliance.py — PDT rule and wash sale detection."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.compliance import _get_avg_cost, check_pdt_compliance, check_wash_sale, count_day_trades
from app.models import Trade


# ---------------------------------------------------------------------------
# _get_avg_cost
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestGetAvgCost:
    def test_no_buys_returns_zero(self, db_session):
        """No buy trades → avg cost is 0."""
        result = _get_avg_cost(db_session, "AAPL", datetime.now(timezone.utc))
        assert result == 0.0

    def test_single_buy(self, db_session):
        trade = Trade(
            ticker="AAPL",
            action="buy",
            quantity=10,
            price=Decimal("150.00"),
            guardrail_passed=True,
            executed=True,
            timestamp=datetime.now(timezone.utc) - timedelta(hours=2),
        )
        db_session.add(trade)
        db_session.commit()

        result = _get_avg_cost(db_session, "AAPL", datetime.now(timezone.utc))
        assert result == pytest.approx(150.0)

    def test_multiple_buys_weighted_average(self, db_session):
        """Average cost from two buys at different prices/quantities."""
        t1 = Trade(
            ticker="AAPL",
            action="buy",
            quantity=10,
            price=Decimal("100.00"),
            guardrail_passed=True,
            executed=True,
            timestamp=datetime.now(timezone.utc) - timedelta(hours=3),
        )
        t2 = Trade(
            ticker="AAPL",
            action="buy",
            quantity=20,
            price=Decimal("130.00"),
            guardrail_passed=True,
            executed=True,
            timestamp=datetime.now(timezone.utc) - timedelta(hours=2),
        )
        db_session.add_all([t1, t2])
        db_session.commit()

        # (10*100 + 20*130) / 30 = (1000 + 2600) / 30 = 120.0
        result = _get_avg_cost(db_session, "AAPL", datetime.now(timezone.utc))
        assert result == pytest.approx(120.0)

    def test_ignores_sells(self, db_session):
        """Sell trades should not affect avg cost calculation."""
        buy = Trade(
            ticker="AAPL",
            action="buy",
            quantity=10,
            price=Decimal("150.00"),
            guardrail_passed=True,
            executed=True,
            timestamp=datetime.now(timezone.utc) - timedelta(hours=3),
        )
        sell = Trade(
            ticker="AAPL",
            action="sell",
            quantity=5,
            price=Decimal("160.00"),
            guardrail_passed=True,
            executed=True,
            timestamp=datetime.now(timezone.utc) - timedelta(hours=2),
        )
        db_session.add_all([buy, sell])
        db_session.commit()

        result = _get_avg_cost(db_session, "AAPL", datetime.now(timezone.utc))
        assert result == pytest.approx(150.0)

    def test_only_buys_before_cutoff(self, db_session):
        """Buys after the 'before' timestamp should be excluded."""
        old_buy = Trade(
            ticker="AAPL",
            action="buy",
            quantity=10,
            price=Decimal("100.00"),
            guardrail_passed=True,
            executed=True,
            timestamp=datetime.now(timezone.utc) - timedelta(hours=5),
        )
        new_buy = Trade(
            ticker="AAPL",
            action="buy",
            quantity=10,
            price=Decimal("200.00"),
            guardrail_passed=True,
            executed=True,
            timestamp=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        db_session.add_all([old_buy, new_buy])
        db_session.commit()

        cutoff = datetime.now(timezone.utc) - timedelta(hours=2)
        result = _get_avg_cost(db_session, "AAPL", cutoff)
        assert result == pytest.approx(100.0)

    def test_ignores_unexecuted_buys(self, db_session):
        """Trades with executed=False should not be counted."""
        trade = Trade(
            ticker="AAPL",
            action="buy",
            quantity=10,
            price=Decimal("150.00"),
            guardrail_passed=True,
            executed=False,
            timestamp=datetime.now(timezone.utc) - timedelta(hours=2),
        )
        db_session.add(trade)
        db_session.commit()

        result = _get_avg_cost(db_session, "AAPL", datetime.now(timezone.utc))
        assert result == 0.0


# ---------------------------------------------------------------------------
# count_day_trades
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestCountDayTrades:
    def test_no_trades(self, db_session):
        """Empty DB → zero day trades."""
        assert count_day_trades(db_session) == 0

    def test_buy_only_no_round_trip(self, db_session):
        """A buy without a same-day sell is not a day trade."""
        trade = Trade(
            ticker="AAPL",
            action="buy",
            quantity=10,
            price=Decimal("150.00"),
            guardrail_passed=True,
            executed=True,
            timestamp=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        db_session.add(trade)
        db_session.commit()

        assert count_day_trades(db_session) == 0

    def test_single_round_trip(self, db_session):
        """A buy and sell of the same ticker on the same day = 1 day trade."""
        # Use naive timestamps firmly in "today" to avoid midnight UTC crossing
        today = datetime.now(timezone.utc).replace(tzinfo=None, hour=10, minute=0)
        buy = Trade(
            ticker="AAPL",
            action="buy",
            quantity=10,
            price=Decimal("150.00"),
            guardrail_passed=True,
            executed=True,
            timestamp=today,
        )
        sell = Trade(
            ticker="AAPL",
            action="sell",
            quantity=10,
            price=Decimal("155.00"),
            guardrail_passed=True,
            executed=True,
            timestamp=today + timedelta(minutes=30),
        )
        db_session.add_all([buy, sell])
        db_session.commit()

        assert count_day_trades(db_session) == 1

    def test_four_day_trades_pdt_violation(self, db_session):
        """4+ day trades in the lookback window is a PDT concern."""
        now = datetime.now(timezone.utc)
        tickers = ["AAPL", "GOOG", "MSFT", "TSLA"]

        for i, ticker in enumerate(tickers):
            buy = Trade(
                ticker=ticker,
                action="buy",
                quantity=1,
                price=Decimal("100.00"),
                guardrail_passed=True,
                executed=True,
                timestamp=now - timedelta(hours=3 + i),
            )
            sell = Trade(
                ticker=ticker,
                action="sell",
                quantity=1,
                price=Decimal("101.00"),
                guardrail_passed=True,
                executed=True,
                timestamp=now - timedelta(hours=2 + i),
            )
            db_session.add_all([buy, sell])

        db_session.commit()
        assert count_day_trades(db_session) == 4

    def test_old_trades_outside_window(self, db_session):
        """Trades outside the lookback window should not count."""
        old_time = datetime.now(timezone.utc) - timedelta(days=10)
        buy = Trade(
            ticker="AAPL",
            action="buy",
            quantity=10,
            price=Decimal("150.00"),
            guardrail_passed=True,
            executed=True,
            timestamp=old_time,
        )
        sell = Trade(
            ticker="AAPL",
            action="sell",
            quantity=10,
            price=Decimal("155.00"),
            guardrail_passed=True,
            executed=True,
            timestamp=old_time + timedelta(hours=1),
        )
        db_session.add_all([buy, sell])
        db_session.commit()

        assert count_day_trades(db_session) == 0

    def test_different_day_not_day_trade(self, db_session):
        """Buy on day 1, sell on day 2 is not a day trade."""
        now = datetime.now(timezone.utc)
        buy = Trade(
            ticker="AAPL",
            action="buy",
            quantity=10,
            price=Decimal("150.00"),
            guardrail_passed=True,
            executed=True,
            timestamp=now - timedelta(days=2),
        )
        sell = Trade(
            ticker="AAPL",
            action="sell",
            quantity=10,
            price=Decimal("155.00"),
            guardrail_passed=True,
            executed=True,
            timestamp=now - timedelta(days=1),
        )
        db_session.add_all([buy, sell])
        db_session.commit()

        assert count_day_trades(db_session) == 0


# ---------------------------------------------------------------------------
# check_pdt_compliance
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestCheckPdtCompliance:
    def test_large_account_always_passes(self, db_session):
        """Accounts >= $25k are exempt from PDT rules."""
        allowed, warning = check_pdt_compliance(db_session, 30000.0, "sell", "AAPL")
        assert allowed is True
        assert warning is None

    def test_buy_action_always_passes(self, db_session):
        """PDT only applies to sells, not buys."""
        allowed, warning = check_pdt_compliance(db_session, 10000.0, "buy", "AAPL")
        assert allowed is True
        assert warning is None

    def test_sell_without_same_day_buy_passes(self, db_session):
        """Selling a stock not bought today is not a day trade."""
        # Buy was yesterday
        buy = Trade(
            ticker="AAPL",
            action="buy",
            quantity=10,
            price=Decimal("150.00"),
            guardrail_passed=True,
            executed=True,
            timestamp=datetime.now(timezone.utc) - timedelta(days=2),
        )
        db_session.add(buy)
        db_session.commit()

        allowed, warning = check_pdt_compliance(db_session, 10000.0, "sell", "AAPL")
        assert allowed is True
        assert warning is None

    def test_pdt_blocked_at_three_day_trades(self, db_session):
        """With 3 existing day trades, a 4th should be blocked for small account."""
        # Use naive timestamps matching what SQLite stores and compliance.py queries
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        # Ensure all trades are firmly "today" (use minutes, not hours, to avoid
        # crossing midnight boundary in UTC)
        today_morning = now.replace(hour=10, minute=0, second=0, microsecond=0)

        # Create 3 existing day-trade round-trips with different tickers
        for i, ticker in enumerate(["GOOG", "MSFT", "TSLA"]):
            buy = Trade(
                ticker=ticker,
                action="buy",
                quantity=1,
                price=Decimal("100.00"),
                guardrail_passed=True,
                executed=True,
                timestamp=today_morning + timedelta(minutes=i * 10),
            )
            sell = Trade(
                ticker=ticker,
                action="sell",
                quantity=1,
                price=Decimal("101.00"),
                guardrail_passed=True,
                executed=True,
                timestamp=today_morning + timedelta(minutes=i * 10 + 5),
            )
            db_session.add_all([buy, sell])

        # Also add a buy of AAPL today (the proposed sell target)
        aapl_buy = Trade(
            ticker="AAPL",
            action="buy",
            quantity=5,
            price=Decimal("150.00"),
            guardrail_passed=True,
            executed=True,
            timestamp=today_morning + timedelta(minutes=60),
        )
        db_session.add(aapl_buy)
        db_session.commit()

        allowed, warning = check_pdt_compliance(db_session, 10000.0, "sell", "AAPL")
        assert allowed is False
        assert "PDT limit" in warning
        assert "AAPL" in warning


# ---------------------------------------------------------------------------
# check_wash_sale
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestCheckWashSale:
    def test_no_recent_sells_no_warning(self, db_session):
        """Buying a ticker with no recent sells → no wash sale warning."""
        allowed, warning = check_wash_sale(db_session, "AAPL", "buy")
        assert allowed is True
        assert warning is None

    def test_sell_action_no_warning(self, db_session):
        """Wash sale check for 'sell' action returns no warning (code only checks 'buy')."""
        allowed, warning = check_wash_sale(db_session, "AAPL", "sell", current_price=100.0)
        assert allowed is True
        assert warning is None

    def test_wash_sale_detected_buy_after_loss(self, db_session):
        """Buying within 30 days of selling at a loss triggers a warning."""
        now = datetime.now(timezone.utc)

        # Buy at 150, then sell at 130 (a loss) 10 days ago
        buy = Trade(
            ticker="AAPL",
            action="buy",
            quantity=10,
            price=Decimal("150.00"),
            guardrail_passed=True,
            executed=True,
            timestamp=now - timedelta(days=15),
        )
        sell = Trade(
            ticker="AAPL",
            action="sell",
            quantity=10,
            price=Decimal("130.00"),
            guardrail_passed=True,
            executed=True,
            timestamp=now - timedelta(days=10),
        )
        db_session.add_all([buy, sell])
        db_session.commit()

        allowed, warning = check_wash_sale(db_session, "AAPL", "buy")
        assert allowed is True  # wash sale only warns, doesn't block
        assert warning is not None
        assert "Wash sale warning" in warning
        assert "AAPL" in warning

    def test_no_wash_sale_when_sold_at_profit(self, db_session):
        """Selling at a profit does not trigger wash sale warning on rebuy."""
        now = datetime.now(timezone.utc)

        buy = Trade(
            ticker="AAPL",
            action="buy",
            quantity=10,
            price=Decimal("150.00"),
            guardrail_passed=True,
            executed=True,
            timestamp=now - timedelta(days=15),
        )
        sell = Trade(
            ticker="AAPL",
            action="sell",
            quantity=10,
            price=Decimal("170.00"),  # sold at profit
            guardrail_passed=True,
            executed=True,
            timestamp=now - timedelta(days=10),
        )
        db_session.add_all([buy, sell])
        db_session.commit()

        allowed, warning = check_wash_sale(db_session, "AAPL", "buy")
        assert allowed is True
        assert warning is None

    def test_no_wash_sale_outside_30_day_window(self, db_session):
        """A loss-sell older than 30 days should not trigger a warning."""
        now = datetime.now(timezone.utc)

        buy = Trade(
            ticker="AAPL",
            action="buy",
            quantity=10,
            price=Decimal("150.00"),
            guardrail_passed=True,
            executed=True,
            timestamp=now - timedelta(days=60),
        )
        sell = Trade(
            ticker="AAPL",
            action="sell",
            quantity=10,
            price=Decimal("130.00"),  # sold at a loss, but > 30 days ago
            guardrail_passed=True,
            executed=True,
            timestamp=now - timedelta(days=35),
        )
        db_session.add_all([buy, sell])
        db_session.commit()

        allowed, warning = check_wash_sale(db_session, "AAPL", "buy")
        assert allowed is True
        assert warning is None

    def test_wash_sale_different_ticker_no_warning(self, db_session):
        """Selling AAPL at a loss then buying GOOG → no wash sale warning."""
        now = datetime.now(timezone.utc)

        buy = Trade(
            ticker="AAPL",
            action="buy",
            quantity=10,
            price=Decimal("150.00"),
            guardrail_passed=True,
            executed=True,
            timestamp=now - timedelta(days=15),
        )
        sell = Trade(
            ticker="AAPL",
            action="sell",
            quantity=10,
            price=Decimal("130.00"),
            guardrail_passed=True,
            executed=True,
            timestamp=now - timedelta(days=10),
        )
        db_session.add_all([buy, sell])
        db_session.commit()

        # Buying GOOG, not AAPL
        allowed, warning = check_wash_sale(db_session, "GOOG", "buy")
        assert allowed is True
        assert warning is None
