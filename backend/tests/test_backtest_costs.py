"""Backtester uses the live cost model (charter §4): assumed half-spread on every fill,
SEC + FINRA fees on sells, estimated tax on net realized gains."""

import json
from datetime import date
from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest

from app.backtest.models import BacktestConfig
from app.strategies import StrategySignal


class _BuyThenSell:
    """Day 1 buy AAPL, day 2 sell it."""
    def decide(self, current_date, indicators, state, bars, params):
        if current_date == date(2026, 3, 2):
            return [StrategySignal(ticker="AAPL", action="buy", reason="t", confidence=1.0)]
        if current_date == date(2026, 3, 3):
            return [StrategySignal(ticker="AAPL", action="sell", reason="t", confidence=1.0)]
        return []


def _bars(closes):
    # Three days: analytics.compute_metrics divides by zero on a 2-point curve
    # (pre-existing; out of scope here).
    closes = closes + [closes[-1]]
    idx = pd.to_datetime(["2026-03-02", "2026-03-03", "2026-03-04"])
    return pd.DataFrame({"open": closes, "high": closes, "low": closes,
                         "close": closes, "volume": [1e6] * 3}, index=idx)


async def _run(db, closes):
    from app.backtest.engine import run_backtest
    cfg = BacktestConfig(name="t", strategy="fake", tickers=json.dumps(["AAPL"]),
                         start_date=date(2026, 3, 2), end_date=date(2026, 3, 4),
                         initial_capital=10_000, params="{}", max_position_pct=0.5,
                         max_positions=5, stop_loss_pct=0.99)
    db.add(cfg)
    db.commit()
    with patch("app.backtest.engine.fetch_and_cache_bars", new=AsyncMock()), \
         patch("app.backtest.engine.load_bars", return_value={"AAPL": _bars(closes)}), \
         patch.dict("app.backtest.engine.STRATEGY_REGISTRY", {"fake": _BuyThenSell}):
        return await run_backtest(cfg, db)


@pytest.mark.integration
class TestBacktestCosts:
    async def test_round_trip_pays_spread_and_fees(self, db_session):
        r = await _run(db_session, [100.0, 110.0])
        assert r.status == "completed", r.error_message
        buy, sell = json.loads(r.trades_log)
        assert buy["spread_cost"] == pytest.approx(2.5)          # 50 sh × $100 × 5 bps
        assert sell["spread_cost"] == pytest.approx(2.75)        # 50 sh × $110 × 5 bps
        assert sell["fee_cost"] == pytest.approx(5500 * 20.60 / 1e6 + 50 * 0.000195)
        final_equity = json.loads(r.equity_curve)[-1]["equity"]
        assert final_equity == pytest.approx(10_000 - 2.5 + 500 - 2.75 - sell["fee_cost"], abs=0.01)

    async def test_after_cost_return_below_gross(self, db_session):
        r = await _run(db_session, [100.0, 110.0])
        # tax 24% × $500 realized = $120 on top of spread + fees
        assert r.total_costs == pytest.approx(2.5 + 2.75 + (5500 * 20.60 / 1e6 + 50 * 0.000195) + 120, abs=0.01)
        assert r.return_after_costs_pct == pytest.approx((10_494.627 - 120) / 10_000 * 100 - 100, abs=0.01)
        assert r.to_summary()["cost_assumptions"]["half_spread_bps"] == 5

    async def test_tax_only_on_net_gains(self, db_session):
        r = await _run(db_session, [100.0, 90.0])  # a loss → no tax
        fees = 4500 * 20.60 / 1e6 + 50 * 0.000195
        assert r.total_costs == pytest.approx(2.5 + 2.25 + fees, abs=0.01)
