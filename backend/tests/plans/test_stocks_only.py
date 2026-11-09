"""Charter §1 / §8 step 5: stocks only. Crypto buys are switched off in code; selling
crypto still works so any old holding can be closed. The crypto machinery stays
(dormant) behind symbols.CRYPTO_ENABLED."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models import Trade
from tests.test_executor_decision_modes import _make_rules_portfolio

_QUOTES = [{"ticker": "BTC/USD", "price": 60_000.0, "change_pct": 0.0, "volume": 1}]


def _broker():
    b = MagicMock()
    b.place_order = AsyncMock(return_value={"order_id": "o", "status": "accepted",
                                            "filled_qty": 0, "stop_order_id": None})
    b.get_order = AsyncMock(return_value={"status": "held", "filled_qty": 0.0, "filled_avg_price": None})
    b.get_bid_ask = AsyncMock(return_value=(None, None))
    return b


async def _run(db, plan, decisions, b):
    from app.plans.executor import run_plan_cycle
    with patch("app.plans.executor.claude_brain.get_trade_decision",
               new_callable=AsyncMock, return_value=decisions), \
         patch("app.plans.executor.broker", b):
        return await run_plan_cycle(db, plan, [], {}, _QUOTES, [], "", "", "")


def _d(action, qty):
    return [{"action": action, "ticker": "BTC/USD", "quantity": qty, "reasoning": "x", "confidence": 0.9}]


def test_crypto_switched_off():
    from app.symbols import CRYPTO_ENABLED
    assert CRYPTO_ENABLED is False


@pytest.mark.integration
class TestStocksOnly:
    async def test_crypto_buy_becomes_hold(self, db_session):
        plan = _make_rules_portfolio(db_session, "claude_decides")
        b = _broker()
        results = await _run(db_session, plan, _d("buy", 0.01), b)
        b.place_order.assert_not_awaited()
        assert results[0]["action"] == "hold"
        assert results[0]["reasoning"].startswith("Stocks only")

    async def test_crypto_sell_still_allowed(self, db_session):
        plan = _make_rules_portfolio(db_session, "claude_decides")
        db_session.add(Trade(portfolio_id=plan.id, ticker="BTC/USD", action="buy", quantity=0.01,
                             price=60_000.0, executed=True, guardrail_passed=True))
        plan.virtual_cash = 9_400.0
        db_session.commit()
        b = _broker()
        results = await _run(db_session, plan, _d("sell", 0.01), b)
        assert results[0]["executed"] is True

    async def test_crypto_overrides_never_enter_the_universe(self, db_session):
        from app.plans.executor import fetch_market_data
        plan = _make_rules_portfolio(db_session, "claude_decides",
                                     strategy_params={"tickers": ["AAPL", "BTC/USD"]})
        with patch("app.plans.executor.broker.get_positions", new=AsyncMock(return_value=[])), \
             patch("app.plans.executor.broker.get_account_balance", new=AsyncMock(return_value={})), \
             patch("app.plans.executor.market_data.get_quotes", new=AsyncMock(return_value=[])), \
             patch("app.plans.executor.market_data.get_news", new=AsyncMock(return_value=[])), \
             patch("app.plans.executor.get_sector_signals", new=AsyncMock(return_value={})), \
             patch("app.plans.executor.get_indicators", new=AsyncMock(return_value={})) as ind:
            await fetch_market_data(db_session, [plan.id], plans=[plan])
        universe = ind.await_args.args[0]
        assert "AAPL" in universe and "BTC/USD" not in universe
