"""Screener → portfolio feed (strategy_params["screener_top_n"]).

A portfolio that opts in gets the latest COMPLETE screener run's top-N tickers
folded into its candidate universe and the ranked CSV in its Claude prompt.
Portfolios that don't opt in must see neither — the feed is per-plan, not
global. Screener failures (no complete run) must never block a cycle.
"""

import pytest
from unittest.mock import AsyncMock, patch

from app.models import Trade  # noqa: F401 — registers all models with Base
from app.screener.models import ScreenerRun, ScreenerCandidate

from tests.test_executor_decision_modes import _make_rules_portfolio


def _seed_screener_run(db, tickers=("AAA", "BBB", "CCC"), status="complete"):
    run = ScreenerRun(universe_size=600, scored_count=len(tickers), status=status)
    db.add(run)
    db.commit()
    db.refresh(run)
    for rank, t in enumerate(tickers, start=1):
        db.add(ScreenerCandidate(
            run_id=run.id, rank=rank, ticker=t, composite_score=1.0 / rank,
            momentum=0.25, rel_strength=0.1, trend_score=1.0, rsi=60.0,
            volatility=0.3, price=50.0,
        ))
    db.commit()
    return run


async def _fetch(db, plan):
    """fetch_market_data with all external boundaries mocked; returns
    (universe handed to get_indicators, screener_csv)."""
    from app.plans import executor

    with patch.object(executor.broker, "get_positions", new=AsyncMock(return_value=[])), \
         patch.object(executor.broker, "get_account_balance",
                      new=AsyncMock(return_value={"cash_available": 1.0, "total_value": 1.0})), \
         patch.object(executor.market_data, "get_quotes", new=AsyncMock(return_value=[])), \
         patch.object(executor.market_data, "get_news", new=AsyncMock(return_value=[])), \
         patch.object(executor, "get_indicators", new=AsyncMock(return_value={})) as mock_ind, \
         patch.object(executor, "get_sector_signals", new=AsyncMock(return_value=[])):
        result = await executor.fetch_market_data(db, [plan.id], plans=[plan])

    return set(mock_ind.call_args.args[0]), result[7]


@pytest.mark.integration
class TestScreenerFeed:
    async def test_opted_in_plan_gets_screener_tickers_and_csv(self, db_session):
        _seed_screener_run(db_session)
        plan = _make_rules_portfolio(db_session, "claude_decides",
                                     strategy_params={"screener_top_n": 2})
        universe, csv = await _fetch(db_session, plan)

        assert {"AAA", "BBB"} <= universe               # top 2 by rank
        assert "CCC" not in universe                    # rank 3 > top_n
        assert "SCREENER TOP CANDIDATES" in csv
        assert "1,AAA" in csv and "2,BBB" in csv

    async def test_non_opted_plan_gets_neither(self, db_session):
        _seed_screener_run(db_session)
        plan = _make_rules_portfolio(db_session, "claude_decides", strategy_params={})
        universe, csv = await _fetch(db_session, plan)

        assert not {"AAA", "BBB", "CCC"} & universe
        assert csv == ""

    async def test_failed_run_is_ignored(self, db_session):
        """Only COMPLETE runs feed trading — a failed refresh can't poison a cycle."""
        _seed_screener_run(db_session, status="failed")
        plan = _make_rules_portfolio(db_session, "claude_decides",
                                     strategy_params={"screener_top_n": 5})
        universe, csv = await _fetch(db_session, plan)

        assert not {"AAA", "BBB", "CCC"} & universe
        assert csv == ""

    async def test_latest_complete_run_wins(self, db_session):
        _seed_screener_run(db_session, tickers=("OLD",))
        _seed_screener_run(db_session, tickers=("NEW",))
        plan = _make_rules_portfolio(db_session, "claude_decides",
                                     strategy_params={"screener_top_n": 5})
        universe, csv = await _fetch(db_session, plan)

        assert "NEW" in universe and "OLD" not in universe

    def test_top_n_sanitization(self, db_session):
        from app.plans.executor import _screener_top_n
        mk = lambda params: _make_rules_portfolio(  # noqa: E731
            db_session, "claude_decides", strategy_params=params)

        assert _screener_top_n(mk({"screener_top_n": 25})) == 25
        assert _screener_top_n(mk({"screener_top_n": 999})) == 40    # capped
        assert _screener_top_n(mk({"screener_top_n": -3})) == 0
        assert _screener_top_n(mk({"screener_top_n": "junk"})) == 0
        assert _screener_top_n(mk({})) == 0

    async def test_csv_gated_per_plan_in_cycle(self, db_session):
        """The shared screener_csv reaches Claude only for opted-in plans."""
        from app.plans.executor import run_plan_cycle

        plan = _make_rules_portfolio(db_session, "claude_decides", strategy_params={})
        balance = {"cash_available": 1000.0, "total_value": 1000.0}
        hold = [{"action": "hold", "ticker": "", "quantity": 0, "reasoning": "", "confidence": 0.0}]
        with patch("app.plans.executor.claude_brain.get_trade_decision",
                   new_callable=AsyncMock, return_value=hold) as mock_claude, \
             patch("app.plans.executor.broker.place_order", new_callable=AsyncMock):
            await run_plan_cycle(db_session, plan, [], balance, [], [], "", "", "",
                                 screener_csv="SCREENER TOP CANDIDATES ...")

        assert mock_claude.await_args.kwargs["screener_csv"] == ""   # not opted in
