"""Crypto support — slash-pair symbols routed correctly at every boundary.

History: "BTC"/"ETH" in prompts once pulled ~$35 phantom prices because the
STOCK data client resolved them to a wrong equities instrument (see
docs/solutions/logic-errors/crypto-tickers-in-stock-client-prompt.md). Crypto
is now supported via Alpaca pair symbology ("BTC/USD") with hard routing:
  - bars/indicators from CryptoHistoricalDataClient, never the stock client
  - orders use TimeInForce.GTC (Alpaca rejects DAY for crypto)
  - Alpha Vantage quotes/news and Finnhub earnings never see slash pairs
"""

import pandas as pd
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models import Trade  # noqa: F401 — registers models with Base
from app.symbols import is_crypto, SUPPORTED_CRYPTO


@pytest.mark.unit
class TestIsCrypto:
    def test_slash_pairs_are_crypto(self):
        assert is_crypto("BTC/USD") and is_crypto("ETH/USD")

    def test_equities_and_etfs_are_not(self):
        for t in ("AAPL", "SPY", "BRK", ""):
            assert not is_crypto(t)

    def test_supported_list_is_all_slash_pairs(self):
        assert all("/" in s for s in SUPPORTED_CRYPTO)


def _bars_df(symbols: list[str], n: int = 60) -> pd.DataFrame:
    idx = pd.MultiIndex.from_tuples(
        [(s, ts) for s in symbols for ts in pd.date_range("2026-01-01", periods=n, freq="D")],
        names=["symbol", "timestamp"],
    )
    return pd.DataFrame(
        {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 1000},
        index=idx,
    )


def _fake_compute(df):
    """Stand-in for _compute_indicators — routing is under test, not pandas_ta."""
    return {"price": float(df["close"].iloc[-1])}


@pytest.mark.unit
class TestIndicatorRouting:
    async def test_crypto_fetched_via_crypto_client_and_merged(self):
        from app import technical_analysis as ta_mod

        ta_mod._indicator_cache.clear()
        ta_mod._cache_date = None
        with patch.object(ta_mod, "_fetch_daily_bars",
                          new=AsyncMock(return_value=_bars_df(["AAPL"]))) as mock_stock, \
             patch.object(ta_mod, "_fetch_daily_crypto_bars",
                          new=AsyncMock(return_value=_bars_df(["BTC/USD"]))) as mock_crypto, \
             patch.object(ta_mod, "_compute_indicators", side_effect=_fake_compute):
            results = await ta_mod.get_indicators(["AAPL", "BTC/USD"])

        mock_stock.assert_awaited_once()
        assert mock_stock.await_args.args[0] == ["AAPL"]          # stock client never sees crypto
        mock_crypto.assert_awaited_once()
        assert mock_crypto.await_args.args[0] == ["BTC/USD"]
        assert "AAPL" in results and "BTC/USD" in results
        assert results["BTC/USD"]["price"] == 100.0

    async def test_crypto_fetch_failure_keeps_stock_indicators(self):
        """One data client failing must not blank the other group's indicators."""
        from app import technical_analysis as ta_mod

        ta_mod._indicator_cache.clear()
        ta_mod._cache_date = None
        with patch.object(ta_mod, "_fetch_daily_bars",
                          new=AsyncMock(return_value=_bars_df(["AAPL"]))), \
             patch.object(ta_mod, "_fetch_daily_crypto_bars",
                          new=AsyncMock(side_effect=RuntimeError("crypto api down"))), \
             patch.object(ta_mod, "_compute_indicators", side_effect=_fake_compute):
            results = await ta_mod.get_indicators(["AAPL", "BTC/USD"])

        assert "AAPL" in results
        assert "BTC/USD" not in results

    async def test_no_crypto_client_call_without_crypto_tickers(self):
        from app import technical_analysis as ta_mod

        ta_mod._indicator_cache.clear()
        ta_mod._cache_date = None
        with patch.object(ta_mod, "_fetch_daily_bars",
                          new=AsyncMock(return_value=_bars_df(["AAPL"]))), \
             patch.object(ta_mod, "_fetch_daily_crypto_bars", new=AsyncMock()) as mock_crypto:
            await ta_mod.get_indicators(["AAPL"])

        mock_crypto.assert_not_awaited()


@pytest.mark.unit
class TestOrderTimeInForce:
    async def _submit(self, ticker):
        from app.brokers import alpaca as alpaca_mod
        from alpaca.trading.enums import TimeInForce

        order = MagicMock()
        order.id, order.status, order.filled_qty = "o1", "accepted", 1.0
        fake_client = MagicMock()
        fake_client.submit_order.return_value = order
        with patch.object(alpaca_mod, "_get_client", return_value=fake_client):
            broker = alpaca_mod.AlpacaBroker()
            await broker.place_order("default", ticker, "buy", 0.5)
        return fake_client.submit_order.call_args.kwargs["order_data"], TimeInForce

    async def test_crypto_orders_use_gtc(self):
        order_data, TimeInForce = await self._submit("BTC/USD")
        assert order_data.time_in_force == TimeInForce.GTC

    async def test_equity_orders_use_day(self):
        order_data, TimeInForce = await self._submit("AAPL")
        assert order_data.time_in_force == TimeInForce.DAY


@pytest.mark.integration
class TestCryptoExcludedFromAlphaVantage:
    async def test_av_quotes_and_news_never_see_slash_pairs(self, db_session):
        """A held BTC/USD position must not leak into AV quote/news calls."""
        from app.plans import executor
        from tests.test_executor_decision_modes import _make_rules_portfolio

        plan = _make_rules_portfolio(db_session, "claude_decides",
                                     strategy_params={"tickers": ["BTC/USD"]})
        db_session.add(Trade(portfolio_id=plan.id, ticker="BTC/USD", action="buy",
                             quantity=0.1, price=50_000.0, executed=True, guardrail_passed=True))
        db_session.commit()

        with patch.object(executor.broker, "get_positions", new=AsyncMock(return_value=[])), \
             patch.object(executor.broker, "get_account_balance",
                          new=AsyncMock(return_value={"cash_available": 1.0, "total_value": 1.0})), \
             patch.object(executor.market_data, "get_quotes", new=AsyncMock(return_value=[])) as mock_q, \
             patch.object(executor.market_data, "get_news", new=AsyncMock(return_value=[])) as mock_n, \
             patch.object(executor, "get_indicators", new=AsyncMock(return_value={})) as mock_ind, \
             patch.object(executor, "get_sector_signals", new=AsyncMock(return_value=[])):
            await executor.fetch_market_data(db_session, [plan.id], plans=[plan])

        # AV boundaries: no slash pairs ever. The only held position is crypto,
        # so the per-ticker quote fan-out shouldn't fire at all — and if a
        # future change makes it fire, it still must exclude pairs.
        if mock_q.await_count:
            assert all("/" not in t for t in mock_q.await_args.args[0])
        news_arg = mock_n.await_args.args[0]
        assert news_arg is None or all("/" not in t for t in news_arg)
        # Alpaca indicators DO see the crypto ticker — that's its price source
        assert "BTC/USD" in set(mock_ind.call_args.args[0])
