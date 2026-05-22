"""Historical OHLCV data pipeline — fetch from Alpaca, cache in PostgreSQL."""

import asyncio
import logging
from collections import defaultdict
from datetime import date, timedelta

import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.backtest.models import OHLCVCache

logger = logging.getLogger(__name__)

_data_client: StockHistoricalDataClient | None = None


def _get_data_client() -> StockHistoricalDataClient:
    global _data_client
    if _data_client is None:
        _data_client = StockHistoricalDataClient(
            settings.ALPACA_API_KEY, settings.ALPACA_SECRET_KEY
        )
    return _data_client


# Alpaca accepts a list of symbols per StockBarsRequest; batching avoids one
# round-trip per ticker. ~500 names → ~5 requests instead of ~500.
_FETCH_CHUNK = 100


async def fetch_and_cache_bars(
    tickers: list[str],
    start: date,
    end: date,
    db: Session,
) -> None:
    """Fetch daily bars from Alpaca and insert into ohlcv_cache.

    Only fetches tickers without full cached coverage (gap-fill), and fetches
    those in multi-symbol batches rather than one request per ticker — critical
    now that the screener scans ~500 names.
    """
    # 1. Coverage check in ONE grouped query (was a SELECT per ticker — an N+1
    #    against the pooler that dominated cost at ~500 screener tickers).
    expected = (end - start).days * 0.7  # ~70% of calendar days are trading days
    cached_by_ticker: dict[str, set] = defaultdict(set)
    for tk, bd in db.execute(
        select(OHLCVCache.ticker, OHLCVCache.bar_date).where(
            OHLCVCache.ticker.in_(tickers),
            OHLCVCache.bar_date >= start,
            OHLCVCache.bar_date <= end,
        )
    ).all():
        cached_by_ticker[tk].add(bd)

    to_fetch = [
        t for t in tickers
        if len(cached_by_ticker.get(t, ())) < expected * 0.9  # incomplete coverage
    ]

    if not to_fetch:
        logger.info("OHLCV cache hit for all %d tickers", len(tickers))
        return

    # 2. Fetch the uncached tickers in multi-symbol chunks.
    client = _get_data_client()
    for i in range(0, len(to_fetch), _FETCH_CHUNK):
        chunk = to_fetch[i:i + _FETCH_CHUNK]
        logger.info("Fetching OHLCV batch: %d tickers (%s..)", len(chunk), chunk[0])
        try:
            request = StockBarsRequest(
                symbol_or_symbols=chunk,
                timeframe=TimeFrame.Day,
                start=start,
                end=end,
            )
            bars = await asyncio.to_thread(client.get_stock_bars, request)
            bars_df = bars.df
            if bars_df.empty:
                logger.warning("No bars returned for batch starting %s", chunk[0])
                continue

            multi = isinstance(bars_df.index, pd.MultiIndex)
            present = set(bars_df.index.get_level_values(0)) if multi else set(chunk)

            for ticker in chunk:
                if ticker not in present:
                    continue
                tdf = bars_df.loc[ticker] if multi else bars_df
                cached_dates = cached_by_ticker.get(ticker, set())
                for ts, row in tdf.iterrows():
                    bar_date = ts.date() if hasattr(ts, "date") else ts
                    if bar_date in cached_dates:
                        continue
                    db.add(OHLCVCache(
                        ticker=ticker,
                        bar_date=bar_date,
                        open=float(row["open"]),
                        high=float(row["high"]),
                        low=float(row["low"]),
                        close=float(row["close"]),
                        volume=int(row["volume"]),
                    ))
            db.commit()
        except Exception as e:
            logger.error("Failed to fetch OHLCV batch starting %s: %s", chunk[0], e)
            db.rollback()


def load_bars(
    tickers: list[str],
    start: date,
    end: date,
    db: Session,
) -> dict[str, pd.DataFrame]:
    """Load cached OHLCV bars from DB into pandas DataFrames.

    Returns {ticker: DataFrame} with DatetimeIndex and
    columns: open, high, low, close, volume.
    """
    result = {}
    for ticker in tickers:
        rows = (
            db.query(OHLCVCache)
            .filter(
                OHLCVCache.ticker == ticker,
                OHLCVCache.bar_date >= start,
                OHLCVCache.bar_date <= end,
            )
            .order_by(OHLCVCache.bar_date)
            .all()
        )

        if not rows:
            continue

        data = {
            "open": [r.open for r in rows],
            "high": [r.high for r in rows],
            "low": [r.low for r in rows],
            "close": [r.close for r in rows],
            "volume": [r.volume for r in rows],
        }
        dates = [pd.Timestamp(r.bar_date) for r in rows]
        df = pd.DataFrame(data, index=dates)
        df.index.name = "timestamp"
        result[ticker] = df

    return result
