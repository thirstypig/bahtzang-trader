"""fetch_and_cache_bars — gap-fill coverage + multi-symbol batching.

The OHLCV cache pipeline is shared infra (backtest, the executor rules path, and
the screener) and was refactored twice — batched multi-symbol fetch, then a
single grouped coverage query — with only manual smoke tests. These exercise the
real SQLite cache logic while mocking the Alpaca boundary, to lock in:
  - a fully-cached ticker is NOT re-fetched (gap-fill)
  - an all-cached request never calls Alpaca at all
  - uncached tickers are fetched in ONE multi-symbol request, not one each
"""

from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from app.backtest.data import fetch_and_cache_bars
from app.backtest.models import OHLCVCache

_END = date.today()
_START = _END - timedelta(days=400)
# 290 daily dates ending today: inside the [start, end] window and above the
# coverage threshold (expected = 400 * 0.7 = 280; skip when cached >= 252).
_DATES = list(pd.date_range(end=pd.Timestamp(_END), periods=290, freq="D"))


def _df_for(symbols: list[str]) -> pd.DataFrame:
    cols = {"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 100}
    if len(symbols) == 1:
        # Alpaca returns a flat (non-MultiIndex) frame for a single symbol.
        return pd.DataFrame(cols, index=pd.DatetimeIndex(_DATES, name="timestamp"))
    tuples = [(s, pd.Timestamp(d)) for s in symbols for d in _DATES]
    return pd.DataFrame(cols, index=pd.MultiIndex.from_tuples(tuples, names=["symbol", "timestamp"]))


def _mock_client(calls: list):
    def fake_get_stock_bars(request):
        syms = request.symbol_or_symbols
        syms = list(syms) if isinstance(syms, (list, tuple)) else [syms]
        calls.append(syms)
        return SimpleNamespace(df=_df_for(syms))

    client = MagicMock()
    client.get_stock_bars.side_effect = fake_get_stock_bars
    return client


def _seed_full_cache(db, ticker: str):
    for d in _DATES:
        db.add(OHLCVCache(ticker=ticker, bar_date=d.date(),
                          open=1.0, high=1.0, low=1.0, close=1.0, volume=100))
    db.commit()


def _cached_count(db, ticker: str) -> int:
    return db.query(OHLCVCache).filter(OHLCVCache.ticker == ticker).count()


@pytest.mark.integration
class TestFetchAndCacheBars:
    async def test_fully_cached_ticker_skipped_only_uncached_fetched(self, db_session):
        _seed_full_cache(db_session, "AAA")  # already fully covered
        calls: list = []
        with patch("app.backtest.data._get_data_client", return_value=_mock_client(calls)):
            await fetch_and_cache_bars(["AAA", "BBB"], _START, _END, db_session)

        assert calls == [["BBB"]]                       # cached ticker skipped, only BBB fetched
        assert _cached_count(db_session, "BBB") == len(_DATES)

    async def test_all_cached_never_calls_alpaca(self, db_session):
        _seed_full_cache(db_session, "AAA")
        calls: list = []
        with patch("app.backtest.data._get_data_client", return_value=_mock_client(calls)):
            await fetch_and_cache_bars(["AAA"], _START, _END, db_session)

        assert calls == []                              # coverage query saw full cache → no fetch

    async def test_uncached_tickers_fetched_in_one_batch(self, db_session):
        calls: list = []
        with patch("app.backtest.data._get_data_client", return_value=_mock_client(calls)):
            await fetch_and_cache_bars(["AAA", "BBB", "CCC"], _START, _END, db_session)

        assert len(calls) == 1                          # one multi-symbol request, not three
        assert set(calls[0]) == {"AAA", "BBB", "CCC"}
        for t in ("AAA", "BBB", "CCC"):
            assert _cached_count(db_session, t) == len(_DATES)


@pytest.mark.integration
class TestLoadBars:
    """load_bars was the third stacked N+1 on the OHLCV path — one SELECT per
    ticker. Pin the single-query rewrite and its output shape."""

    def test_one_query_regardless_of_ticker_count(self, db_session):
        from sqlalchemy import event
        from app.backtest.data import load_bars

        _seed_full_cache(db_session, "AAA")
        _seed_full_cache(db_session, "BBB")

        selects: list[str] = []

        def _count(conn, cursor, statement, parameters, context, executemany):
            if statement.lstrip().upper().startswith("SELECT"):
                selects.append(statement)

        engine = db_session.get_bind()
        event.listen(engine, "before_cursor_execute", _count)
        try:
            bars = load_bars(["AAA", "BBB"], _START, _END, db_session)
        finally:
            event.remove(engine, "before_cursor_execute", _count)

        assert len(selects) == 1                        # grouped query, not per-ticker
        assert set(bars) == {"AAA", "BBB"}

    def test_dataframe_shape_and_order(self, db_session):
        from app.backtest.data import load_bars

        _seed_full_cache(db_session, "AAA")
        bars = load_bars(["AAA", "MISSING"], _START, _END, db_session)

        assert "MISSING" not in bars                    # uncached ticker silently absent
        df = bars["AAA"]
        assert list(df.columns) == ["open", "high", "low", "close", "volume"]
        assert len(df) == len(_DATES)
        assert df.index.is_monotonic_increasing         # ordered by bar_date
        assert df.index.name == "timestamp"
