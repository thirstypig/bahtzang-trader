"""Historical OHLCV data pipeline — fetch from Alpaca, cache in PostgreSQL."""

import asyncio
import logging
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


async def fetch_and_cache_bars(
    tickers: list[str],
    start: date,
    end: date,
    db: Session,
) -> None:
    """Fetch daily bars from Alpaca and insert into ohlcv_cache.

    Only fetches date ranges not already cached (gap-fill logic).
    """
    for ticker in tickers:
        # Find what's already cached
        cached_dates = set(
            row[0]
            for row in db.execute(
                select(OHLCVCache.bar_date).where(
                    OHLCVCache.ticker == ticker,
                    OHLCVCache.bar_date >= start,
                    OHLCVCache.bar_date <= end,
                )
            ).all()
        )

        if cached_dates:
            # Check if we have full coverage (allow ~10% missing for holidays)
            expected = (end - start).days * 0.7  # ~70% are trading days
            if len(cached_dates) >= expected * 0.9:
                logger.info("Cache hit for %s (%d bars)", ticker, len(cached_dates))
                continue

        logger.info("Fetching OHLCV for %s: %s to %s", ticker, start, end)
        try:
            client = _get_data_client()
            request = StockBarsRequest(
                symbol_or_symbols=[ticker],
                timeframe=TimeFrame.Day,
                start=start,
                end=end,
            )
            bars = await asyncio.to_thread(client.get_stock_bars, request)
            bars_df = bars.df

            if bars_df.empty:
                logger.warning("No bars returned for %s", ticker)
                continue

            # Handle multi-index (symbol, timestamp)
            if isinstance(bars_df.index, pd.MultiIndex):
                if ticker in bars_df.index.get_level_values(0):
                    bars_df = bars_df.loc[ticker]
                else:
                    logger.warning("Ticker %s not found in response", ticker)
                    continue

            count = 0
            for ts, row in bars_df.iterrows():
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
                count += 1

            db.commit()
            logger.info("Cached %d new bars for %s", count, ticker)

        except Exception as e:
            logger.error("Failed to fetch bars for %s: %s", ticker, e)
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
