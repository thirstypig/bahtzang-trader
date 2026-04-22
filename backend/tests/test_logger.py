"""Integration tests for app/logger.py.

Tests the log_trade function that persists trade decisions to the DB.
"""

import pytest
from decimal import Decimal

from app.models import Trade
from app.logger import log_trade


@pytest.mark.integration
class TestLogTrade:
    def test_creates_trade_in_db(self, db_session):
        """log_trade should create a Trade row in the database."""
        log_trade(
            db=db_session,
            ticker="AAPL",
            action="buy",
            quantity=10.0,
            price=150.50,
            claude_reasoning="Strong momentum signal",
            confidence=0.85,
            guardrail_passed=True,
            guardrail_block_reason=None,
            executed=True,
        )

        trades = db_session.query(Trade).all()
        assert len(trades) == 1
        assert trades[0].ticker == "AAPL"

    def test_returns_trade_with_correct_fields(self, db_session):
        """log_trade should return the Trade object with all fields set."""
        trade = log_trade(
            db=db_session,
            ticker="MSFT",
            action="sell",
            quantity=5.0,
            price=420.75,
            claude_reasoning="Overbought RSI, taking profit",
            confidence=0.72,
            guardrail_passed=True,
            guardrail_block_reason=None,
            executed=True,
        )

        assert isinstance(trade, Trade)
        assert trade.id is not None
        assert trade.ticker == "MSFT"
        assert trade.action == "sell"
        assert trade.quantity == 5.0
        assert float(trade.price) == pytest.approx(420.75)
        assert trade.claude_reasoning == "Overbought RSI, taking profit"
        assert trade.confidence == 0.72
        assert trade.guardrail_passed is True
        assert trade.guardrail_block_reason is None
        assert trade.executed is True
        assert trade.timestamp is not None

    def test_handles_none_price_for_hold(self, db_session):
        """Hold trades have price=None — log_trade should handle gracefully."""
        trade = log_trade(
            db=db_session,
            ticker="AAPL",
            action="hold",
            quantity=0,
            price=None,
            claude_reasoning="No clear signal, holding position",
            confidence=0.45,
            guardrail_passed=True,
            guardrail_block_reason=None,
            executed=False,
        )

        assert isinstance(trade, Trade)
        assert trade.price is None
        assert trade.action == "hold"
        assert trade.executed is False

        # Verify it persisted
        persisted = db_session.query(Trade).filter_by(id=trade.id).one()
        assert persisted.price is None

    def test_blocked_trade_with_reason(self, db_session):
        """Guardrail-blocked trade stores the block reason."""
        trade = log_trade(
            db=db_session,
            ticker="GME",
            action="buy",
            quantity=100.0,
            price=25.00,
            claude_reasoning="Momentum play",
            confidence=0.55,
            guardrail_passed=False,
            guardrail_block_reason="Confidence below minimum threshold (0.60)",
            executed=False,
        )

        assert trade.guardrail_passed is False
        assert trade.guardrail_block_reason == "Confidence below minimum threshold (0.60)"
        assert trade.executed is False
