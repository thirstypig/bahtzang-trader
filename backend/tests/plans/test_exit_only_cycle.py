"""Exit-only afternoon cycle — buys suppressed, sells proceed, P&L visible.

The 3:30 PM exit check exists to manage risk on open positions between daily
trading cycles. These tests pin the two safety properties it depends on:
  - exit_only suppresses buys for EVERY decision mode at one enforcement
    point in the executor (the Claude prompt alone is not a guarantee)
  - sells still execute, so the cycle can actually cut a loser
  - virtual positions reach Claude with real cost basis / unrealized P&L
"""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, patch

# Force all models to register with Base.metadata before db_engine fixture
from app.models import Trade  # noqa: F401

from tests.test_executor_decision_modes import _make_rules_portfolio

_QUOTES = [{"ticker": "AAPL", "price": 150.0, "change_pct": 0.5, "volume": 1_000_000}]
_BALANCE = {"cash_available": 50_000.0, "total_value": 100_000.0}

# Factory functions, not module constants — the executor mutates decision
# dicts in place (buy→hold coercion), so shared dicts leak across tests.
def _buy():
    return [{"action": "buy", "ticker": "AAPL", "quantity": 5.0, "reasoning": "Buy signal", "confidence": 0.75}]


def _sell():
    return [{"action": "sell", "ticker": "AAPL", "quantity": 2.0, "reasoning": "Cut loser", "confidence": 0.8}]


async def _run_cycle(db, plan, exit_only=False):
    from app.plans.executor import run_plan_cycle
    return await run_plan_cycle(
        db, plan, [], _BALANCE, _QUOTES, [], "", "", "", exit_only=exit_only,
    )


def _seed_position(db, plan, ticker="AAPL", qty=2.0, price=100.0):
    """Insert an executed buy so the plan holds a virtual position."""
    t = Trade(
        portfolio_id=plan.id, ticker=ticker, action="buy", quantity=qty,
        price=price, executed=True, guardrail_passed=True,
    )
    db.add(t)
    db.commit()


@pytest.mark.integration
class TestExitOnlySuppressesBuys:
    async def test_claude_buy_suppressed_to_hold(self, db_session):
        plan = _make_rules_portfolio(db_session, "claude_decides")
        with patch("app.plans.executor.claude_brain.get_trade_decision",
                   new_callable=AsyncMock, return_value=_buy()) as mock_claude, \
             patch("app.plans.executor.broker.place_order", new_callable=AsyncMock) as mock_order:
            results = await _run_cycle(db_session, plan, exit_only=True)

        assert results[0]["action"] == "hold"
        assert "Exit-only cycle: buy suppressed" in results[0]["reasoning"]
        mock_order.assert_not_awaited()                 # nothing reached the broker
        # The Claude call itself was told it's an exit cycle
        assert mock_claude.await_args.kwargs["exit_only"] is True

    async def test_rules_buy_suppressed_to_hold(self, db_session):
        """Rules strategies know nothing about exit cycles — the executor must filter."""
        plan = _make_rules_portfolio(db_session, "rules_decide")
        with patch("app.plans.executor._get_strategy_decisions",
                   new_callable=AsyncMock, return_value=_buy()), \
             patch("app.plans.executor.broker.place_order", new_callable=AsyncMock) as mock_order:
            results = await _run_cycle(db_session, plan, exit_only=True)

        assert results[0]["action"] == "hold"
        mock_order.assert_not_awaited()

    async def test_sell_still_executes_on_exit_cycle(self, db_session):
        plan = _make_rules_portfolio(db_session, "claude_decides")
        _seed_position(db_session, plan, qty=2.0, price=100.0)
        with patch("app.plans.executor.claude_brain.get_trade_decision",
                   new_callable=AsyncMock, return_value=_sell()), \
             patch("app.plans.executor.broker.place_order",
                   new_callable=AsyncMock, return_value={"order_id": "x1"}) as mock_order:
            results = await _run_cycle(db_session, plan, exit_only=True)

        assert results[0]["action"] == "sell"
        assert results[0]["executed"] is True
        mock_order.assert_awaited_once()

    async def test_normal_cycle_buys_unaffected(self, db_session):
        """exit_only defaults to False — the morning cycle still buys."""
        plan = _make_rules_portfolio(db_session, "claude_decides")
        with patch("app.plans.executor.claude_brain.get_trade_decision",
                   new_callable=AsyncMock, return_value=_buy()) as mock_claude, \
             patch("app.plans.executor.broker.place_order",
                   new_callable=AsyncMock, return_value={"order_id": "x2"}):
            results = await _run_cycle(db_session, plan, exit_only=False)

        assert results[0]["action"] == "buy"
        assert mock_claude.await_args.kwargs["exit_only"] is False


@pytest.mark.integration
class TestVirtualPositionPnL:
    async def test_positions_carry_cost_basis_and_pnl(self, db_session):
        """Claude must see real P&L: bought 2 @ $100, quoted at $150 → +50%."""
        plan = _make_rules_portfolio(db_session, "claude_decides")
        _seed_position(db_session, plan, qty=2.0, price=100.0)
        with patch("app.plans.executor.claude_brain.get_trade_decision",
                   new_callable=AsyncMock, return_value=[
                       {"action": "hold", "ticker": "", "quantity": 0,
                        "reasoning": "", "confidence": 0.0}]) as mock_claude, \
             patch("app.plans.executor.broker.place_order", new_callable=AsyncMock):
            await _run_cycle(db_session, plan)

        positions = mock_claude.await_args.kwargs["positions"]
        aapl = next(p for p in positions if p["instrument"]["symbol"] == "AAPL")
        assert aapl["cost_basis"] == 200.0
        assert aapl["unrealized_pnl"] == 100.0          # 2 × ($150 − $100)
        assert aapl["unrealized_pnl_pct"] == 50.0

    def test_average_cost_method(self, db_session):
        """Buys re-average; sells reduce qty at unchanged average."""
        from app.plans.executor import compute_virtual_cost_basis
        plan = _make_rules_portfolio(db_session, "claude_decides")
        for action, qty, price in [("buy", 1.0, 100.0), ("buy", 1.0, 200.0), ("sell", 1.0, 300.0)]:
            db_session.add(Trade(portfolio_id=plan.id, ticker="AAPL", action=action,
                                 quantity=qty, price=price, executed=True, guardrail_passed=True))
        db_session.commit()

        basis = compute_virtual_cost_basis(db_session, plan.id)
        assert basis == {"AAPL": 150.0}                 # (100+200)/2, sell doesn't re-average

    def test_closed_position_has_no_basis(self, db_session):
        from app.plans.executor import compute_virtual_cost_basis
        plan = _make_rules_portfolio(db_session, "claude_decides")
        for action, qty in [("buy", 2.0), ("sell", 2.0)]:
            db_session.add(Trade(portfolio_id=plan.id, ticker="AAPL", action=action,
                                 quantity=qty, price=100.0, executed=True, guardrail_passed=True))
        db_session.commit()

        assert compute_virtual_cost_basis(db_session, plan.id) == {}
