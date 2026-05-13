"""Tests for executor decision-mode branching.

Verifies that:
  - claude_decides mode calls get_trade_decision (unchanged)
  - rules_decide mode calls _get_strategy_decisions, never Claude
  - rules_with_claude_oversight calls both and logs rules_recommendation
  - Trading constraints (cooldown, frequency) still block rules-mode signals
"""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, patch

# Force all models to register with Base.metadata before db_engine fixture
# calls create_all() — without this, the portfolios/trades tables don't exist.
from app.models import Trade  # noqa: F401 (triggers app.plans.models import chain)

from tests.conftest import make_plan


# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------

def _make_rules_portfolio(db_session, decision_mode, strategy_id="sma_crossover", strategy_params=None):
    """Insert a Portfolio row configured for the given decision mode."""
    from app.plans.models import Portfolio

    p = Portfolio(
        name=f"Test {decision_mode}",
        budget=Decimal("10000"),
        virtual_cash=Decimal("10000"),
        trading_goal="maximize_returns",
        risk_profile="moderate",
        trading_frequency="1x",
        is_active=True,
        decision_mode=decision_mode,
        strategy_id=strategy_id,
        strategy_params=strategy_params or {},
        cooldown_hours=48,
        min_confidence=Decimal("0.55"),
        respect_wash_sale=True,
        kelly_fraction=Decimal("0.15"),
        circuit_breaker_daily_pct=Decimal("-5.0"),
        circuit_breaker_weekly_pct=Decimal("-10.0"),
    )
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


# Canned decisions
_HOLD = [{"action": "hold", "ticker": "", "quantity": 0, "reasoning": "No signal", "confidence": 0.0}]
_BUY_AAPL = [{"action": "buy", "ticker": "AAPL", "quantity": 5.0, "reasoning": "Buy signal", "confidence": 0.75}]

# Shared fake market context (enough for the executor to price AAPL without a network call)
_QUOTES = [{"ticker": "AAPL", "price": 150.0, "change_pct": 0.5, "volume": 1_000_000}]
_BALANCE = {"cash_available": 50_000.0, "total_value": 100_000.0}


async def _run_cycle(db, plan, quotes=None):
    """Thin wrapper: calls run_plan_cycle with minimal arguments."""
    from app.plans.executor import run_plan_cycle
    return await run_plan_cycle(db, plan, [], _BALANCE, quotes or _QUOTES, [], "", "", "")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestClaudeDecidesModeUnchanged:
    """claude_decides path must not change — existing behaviour preserved."""

    async def test_claude_decides_mode_unchanged(self, db_session):
        plan = _make_rules_portfolio(db_session, "claude_decides")

        with patch("app.plans.executor.claude_brain.get_trade_decision", new_callable=AsyncMock) as mock_claude, \
             patch("app.plans.executor.broker.place_order", new_callable=AsyncMock):
            mock_claude.return_value = _HOLD
            results = await _run_cycle(db_session, plan)

        mock_claude.assert_called_once()
        assert results[0]["action"] == "hold"


@pytest.mark.integration
class TestRulesDecideMode:

    async def test_rules_decide_mode_skips_claude(self, db_session):
        """rules_decide never calls the Anthropic API."""
        plan = _make_rules_portfolio(db_session, "rules_decide")

        with patch("app.plans.executor._get_strategy_decisions", new_callable=AsyncMock) as mock_strat, \
             patch("app.plans.executor.claude_brain.get_trade_decision", new_callable=AsyncMock) as mock_claude, \
             patch("app.plans.executor.broker.place_order", new_callable=AsyncMock):
            mock_strat.return_value = _HOLD
            results = await _run_cycle(db_session, plan)

        mock_claude.assert_not_called()
        mock_strat.assert_called_once()
        assert results[0]["action"] == "hold"

    async def test_rules_decide_mode_emits_correct_signal_for_dual_momentum_mock(self, db_session):
        """Strategy buy signal is sized, logged as a Trade row, and not mangled."""
        plan = _make_rules_portfolio(db_session, "rules_decide", strategy_id="dual_momentum")

        with patch("app.plans.executor._get_strategy_decisions", new_callable=AsyncMock) as mock_strat, \
             patch("app.plans.executor.broker.place_order", new_callable=AsyncMock) as mock_order:
            mock_strat.return_value = list(_BUY_AAPL)  # copy so pop() doesn't mutate the constant
            mock_order.return_value = {"order_id": "dm-order-001"}
            results = await _run_cycle(db_session, plan)

        from app.models import Trade
        assert results[0]["action"] == "buy"
        assert results[0]["ticker"] == "AAPL"
        assert results[0]["executed"] is True

        trade = db_session.query(Trade).filter(Trade.portfolio_id == plan.id).first()
        assert trade is not None
        assert trade.action == "buy"
        assert trade.ticker == "AAPL"
        # No Claude review → rules_recommendation is null
        assert trade.rules_recommendation is None

    async def test_rules_mode_still_blocks_on_cooldown(self, db_session):
        """Constraint enforcement runs even for rules_decide — strategy signal blocked."""
        plan = _make_rules_portfolio(db_session, "rules_decide")

        with patch("app.plans.executor._get_strategy_decisions", new_callable=AsyncMock) as mock_strat, \
             patch("app.plans.executor.check_trading_constraints", new_callable=AsyncMock) as mock_constraints, \
             patch("app.plans.executor.broker.place_order", new_callable=AsyncMock):
            mock_strat.return_value = [{"action": "buy", "ticker": "AAPL", "quantity": 5, "reasoning": "signal", "confidence": 0.8}]
            mock_constraints.return_value = (False, "Cooldown: AAPL touched 12.0h ago, need 48h")
            results = await _run_cycle(db_session, plan)

        assert results[0]["action"] == "hold"
        assert "Cooldown" in results[0]["reasoning"]
        assert results[0]["executed"] is False

        # Trade IS logged (for audit trail) but not executed
        from app.models import Trade
        trade = db_session.query(Trade).filter(Trade.portfolio_id == plan.id).first()
        assert trade is not None
        assert trade.executed is False


@pytest.mark.integration
class TestOversightMode:

    async def test_oversight_mode_calls_both(self, db_session):
        """rules_with_claude_oversight runs strategy AND Claude review."""
        plan = _make_rules_portfolio(db_session, "rules_with_claude_oversight")

        # New per-decision return format: {confirmed, override_decision, reasoning, override_confidence}
        confirmed_review = {
            "confirmed": True,
            "override_decision": None,
            "reasoning": "Signal is valid",
            "override_confidence": 0.0,
        }

        with patch("app.plans.executor._get_strategy_decisions", new_callable=AsyncMock) as mock_strat, \
             patch("app.plans.executor.claude_brain.review_trade_decision", new_callable=AsyncMock) as mock_review, \
             patch("app.plans.executor.broker.place_order", new_callable=AsyncMock):
            mock_strat.return_value = list(_HOLD)
            mock_review.return_value = confirmed_review
            results = await _run_cycle(db_session, plan)

        mock_strat.assert_called_once()
        # Called once per strategy decision (one hold → one review call)
        mock_review.assert_called_once()
        assert results[0]["action"] == "hold"

    async def test_oversight_mode_logs_both_decisions(self, db_session):
        """Trade row stores the strategy's original signal AND the final (overridden) action."""
        plan = _make_rules_portfolio(db_session, "rules_with_claude_oversight")

        original = {"action": "buy", "ticker": "AAPL", "quantity": 3.0, "reasoning": "SMA crossover", "confidence": 0.7}
        # Claude disagrees and overrides to hold
        override_review = {
            "confirmed": False,
            "override_decision": {
                "action": "hold",
                "ticker": "AAPL",
                "quantity": 0,
                "reasoning": "market overvalued",
                "confidence": 0.5,
            },
            "reasoning": "market overvalued",
            "override_confidence": 0.5,
        }

        with patch("app.plans.executor._get_strategy_decisions", new_callable=AsyncMock) as mock_strat, \
             patch("app.plans.executor.claude_brain.review_trade_decision", new_callable=AsyncMock) as mock_review, \
             patch("app.plans.executor.broker.place_order", new_callable=AsyncMock):
            mock_strat.return_value = [original.copy()]
            mock_review.return_value = override_review
            results = await _run_cycle(db_session, plan)

        # Final action is hold (Claude override)
        assert results[0]["action"] == "hold"

        from app.models import Trade
        trade = db_session.query(Trade).filter(Trade.portfolio_id == plan.id).first()
        assert trade is not None
        assert trade.action == "hold"
        # Strategy's original buy signal is preserved in the audit column
        assert trade.rules_recommendation is not None
        assert trade.rules_recommendation["action"] == "buy"
        assert trade.rules_recommendation["ticker"] == "AAPL"
        assert trade.rules_recommendation["confidence"] == pytest.approx(0.7)
