"""fetch_market_data must fold each plan's strategy_params['tickers'] into the
universe it fetches for the claude_decides path.

Regression (the bug that motivated widening the universe): the Claude data path
built its ticker set from broker positions + GOAL_WATCHLIST only and silently
ignored strategy_params['tickers']. Only the rules-strategy path honored that
param, so a Claude-mode portfolio's universe override — and, later, a daily
screener's top-candidate list — never reached the market-data fetch or Claude.
"""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, patch

# Register models with Base.metadata before db fixtures create_all()
from app.models import Trade  # noqa: F401


def _make_plan(db, strategy_params):
    from app.plans.models import Portfolio

    p = Portfolio(
        name="universe-test",
        budget=Decimal("10000"),
        virtual_cash=Decimal("10000"),
        trading_goal="maximize_returns",
        risk_profile="moderate",
        trading_frequency="1x",
        is_active=True,
        decision_mode="claude_decides",
        strategy_params=strategy_params,
        kelly_fraction=Decimal("0.15"),
        min_confidence=Decimal("0.55"),
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


async def _universe_passed_to_fetch(db, plan) -> set[str]:
    """Run fetch_market_data with every external boundary mocked, and return the
    ticker set it handed to get_indicators (== the assembled universe)."""
    from app.plans import executor

    with patch.object(executor.broker, "get_positions", new=AsyncMock(return_value=[])), \
         patch.object(executor.broker, "get_account_balance",
                      new=AsyncMock(return_value={"cash_available": 1.0, "total_value": 1.0})), \
         patch.object(executor.market_data, "get_quotes", new=AsyncMock(return_value=[])), \
         patch.object(executor.market_data, "get_news", new=AsyncMock(return_value=[])), \
         patch.object(executor, "get_indicators", new=AsyncMock(return_value={})) as mock_ind, \
         patch.object(executor, "get_sector_signals", new=AsyncMock(return_value=[])):
        await executor.fetch_market_data(db, [plan.id], plans=[plan])

    return set(mock_ind.call_args.args[0])


@pytest.mark.integration
class TestFetchMarketDataUniverse:
    async def test_strategy_params_tickers_reach_the_universe(self, db_session):
        """An override ticker is fetched alongside the goal watchlist."""
        plan = _make_plan(db_session, {"tickers": ["ZZZZ"]})

        universe = await _universe_passed_to_fetch(db_session, plan)

        assert "ZZZZ" in universe  # the override actually reached the fetch
        assert "AAPL" in universe  # goal watchlist is still unioned in

    async def test_malformed_tickers_param_is_ignored(self, db_session):
        """A non-list param is skipped — not crashed on, not splattered into chars."""
        plan = _make_plan(db_session, {"tickers": "AAPL,MSFT"})  # a str, not a list

        universe = await _universe_passed_to_fetch(db_session, plan)

        assert "AAPL,MSFT" not in universe  # not added whole
        assert "A" not in universe and "," not in universe  # not iterated char-by-char

    async def test_quotes_not_fanned_over_the_universe(self, db_session):
        """Alpha Vantage quotes cover only held positions, never the full watchlist.

        Guards the fix that stopped the ~100-call AV fan-out from burning the
        free-tier daily quota (which is shared with the get_news call). With no
        held positions, get_quotes must not be called at all — even though the
        indicator batch still covers the whole candidate universe.
        """
        from app.plans import executor

        plan = _make_plan(db_session, {})  # no positions, no override

        with patch.object(executor.broker, "get_positions", new=AsyncMock(return_value=[])), \
             patch.object(executor.broker, "get_account_balance",
                          new=AsyncMock(return_value={"cash_available": 1.0, "total_value": 1.0})), \
             patch.object(executor.market_data, "get_quotes", new=AsyncMock(return_value=[])) as mock_q, \
             patch.object(executor.market_data, "get_news", new=AsyncMock(return_value=[])), \
             patch.object(executor, "get_indicators", new=AsyncMock(return_value={})) as mock_ind, \
             patch.object(executor, "get_sector_signals", new=AsyncMock(return_value=[])):
            await executor.fetch_market_data(db_session, [plan.id], plans=[plan])

        assert "AAPL" in set(mock_ind.call_args.args[0])  # indicators still cover the universe
        mock_q.assert_not_called()  # but quotes were NOT fanned out over it
