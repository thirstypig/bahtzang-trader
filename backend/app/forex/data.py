"""Forex OHLCV fetcher: yfinance source with DB cache, plus weekly resample."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
from sqlalchemy.orm import Session

from app.forex.models import ForexBar


YFINANCE_SYMBOL = {
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "USDJPY=X",
    "AUDUSD": "AUDUSD=X",
    "USDCAD": "USDCAD=X",
    "USDCHF": "USDCHF=X",
    "NZDUSD": "NZDUSD=X",
}


def _yf_fetch(symbol: str, start: date, end: date) -> pd.DataFrame:
    import yfinance as yf
    yf_symbol = YFINANCE_SYMBOL.get(symbol, symbol)
    ticker = yf.Ticker(yf_symbol)
    hist = ticker.history(start=start, end=end + timedelta(days=1), interval="1d")
    if hist.empty:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close"])
    return pd.DataFrame({
        "date": [d.date() for d in hist.index],
        "open": hist["Open"].to_numpy(),
        "high": hist["High"].to_numpy(),
        "low": hist["Low"].to_numpy(),
        "close": hist["Close"].to_numpy(),
    })


def fetch_daily_bars(
    symbol: str,
    start: date,
    end: date,
    db: Session | None = None,
) -> pd.DataFrame:
    """Return daily OHLCV for `symbol` over [start, end]. Cached in DB if `db` given.

    Cache is "good enough" — if the cache covers the requested range with at most
    a handful of missing weekday rows (FX markets occasionally have data gaps),
    we serve from cache. Otherwise we refetch from yfinance and upsert.
    """
    if db is not None:
        cached = (
            db.query(ForexBar)
            .filter(ForexBar.symbol == symbol)
            .filter(ForexBar.bar_date >= start)
            .filter(ForexBar.bar_date <= end)
            .order_by(ForexBar.bar_date)
            .all()
        )
        if cached:
            cached_dates = {b.bar_date for b in cached}
            full_range = [d.date() for d in pd.bdate_range(start, end)]
            missing = [d for d in full_range if d not in cached_dates]
            if len(missing) <= 5:
                return pd.DataFrame([{
                    "date": b.bar_date, "open": b.open, "high": b.high,
                    "low": b.low, "close": b.close,
                } for b in cached])

    df = _yf_fetch(symbol, start, end)

    if db is not None and not df.empty:
        existing_dates = {
            row[0] for row in db.query(ForexBar.bar_date)
            .filter(ForexBar.symbol == symbol)
            .filter(ForexBar.bar_date >= start)
            .filter(ForexBar.bar_date <= end)
            .all()
        }
        new_rows = [
            ForexBar(
                symbol=symbol,
                bar_date=row["date"],
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
            )
            for _, row in df.iterrows()
            if row["date"] not in existing_dates
        ]
        if new_rows:
            db.add_all(new_rows)
            db.commit()

    return df


def resample_to_weekly(daily_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate daily bars to weekly (week ending Friday)."""
    if daily_df.empty:
        return daily_df.copy()
    df = daily_df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    weekly = df.resample("W-FRI").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
    }).dropna()
    weekly = weekly.reset_index()
    weekly["date"] = weekly["date"].dt.date
    return weekly
