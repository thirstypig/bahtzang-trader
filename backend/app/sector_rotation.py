"""Sector rotation signals — relative strength of sector ETFs vs SPY.

Computes whether each sector is LEADING or LAGGING the S&P 500
based on relative strength ratio vs its 50-day moving average.
"""

import asyncio
import logging
from datetime import date, timedelta

import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from app.config import settings

logger = logging.getLogger(__name__)

SECTOR_ETFS = [
    "XLK", "XLV", "XLF", "XLE", "XLI",
    "XLY", "XLP", "XLB", "XLRE", "XLU", "XLC",
]

# Cache: recomputed once per trading day
_sector_cache: list[dict] | None = None
_sector_cache_date: date | None = None

_data_client: StockHistoricalDataClient | None = None


def _get_data_client() -> StockHistoricalDataClient:
    global _data_client
    if _data_client is None:
        _data_client = StockHistoricalDataClient(
            settings.ALPACA_API_KEY, settings.ALPACA_SECRET_KEY
        )
    return _data_client


async def get_sector_signals() -> list[dict]:
    """Return sector rotation signals, cached daily."""
    global _sector_cache, _sector_cache_date

    today = date.today()
    if _sector_cache_date == today and _sector_cache is not None:
        return _sector_cache

    logger.info("Computing sector rotation signals")

    try:
        client = _get_data_client()
        all_symbols = SECTOR_ETFS + ["SPY"]
        end = today
        start = end - timedelta(days=120)  # ~80 trading days for 50-day RS SMA

        request = StockBarsRequest(
            symbol_or_symbols=all_symbols,
            timeframe=TimeFrame.Day,
            start=start,
            end=end,
        )
        bars = await asyncio.to_thread(client.get_stock_bars, request)
        df = bars.df

        if "SPY" not in df.index.get_level_values(0):
            logger.warning("SPY data not available for sector rotation")
            return []

        spy_close = df.loc["SPY"]["close"]

        signals = []
        for etf in SECTOR_ETFS:
            try:
                if etf not in df.index.get_level_values(0):
                    continue

                etf_close = df.loc[etf]["close"]

                # Relative strength ratio: ETF / SPY
                # Align on common dates
                common = etf_close.index.intersection(spy_close.index)
                if len(common) < 50:
                    continue

                etf_aligned = etf_close.loc[common]
                spy_aligned = spy_close.loc[common]
                ratio = etf_aligned / spy_aligned
                ratio_sma50 = ratio.rolling(50).mean()

                latest_ratio = float(ratio.iloc[-1])
                latest_sma = float(ratio_sma50.iloc[-1])

                # Performance
                perf_1m = (float(etf_aligned.iloc[-1]) / float(etf_aligned.iloc[-21]) - 1) * 100 if len(etf_aligned) >= 21 else 0
                perf_3m = (float(etf_aligned.iloc[-1]) / float(etf_aligned.iloc[-63]) - 1) * 100 if len(etf_aligned) >= 63 else 0

                # RSI
                rsi = etf_close.pct_change().rolling(14).apply(
                    lambda x: 100 - (100 / (1 + (x[x > 0].mean() / abs(x[x < 0].mean())))) if abs(x[x < 0].mean()) > 0 else 50,
                    raw=False,
                )
                rsi_val = round(float(rsi.iloc[-1]), 1) if not rsi.empty else None

                signals.append({
                    "etf": etf,
                    "rs_trend": "LEADING" if latest_ratio > latest_sma else "LAGGING",
                    "perf_1m": round(perf_1m, 1),
                    "perf_3m": round(perf_3m, 1),
                    "rsi14": rsi_val,
                })
            except Exception as e:
                logger.warning("Failed to compute sector signal for %s: %s", etf, e)

        # Sort by 3-month performance descending
        signals.sort(key=lambda x: x.get("perf_3m", 0), reverse=True)

        _sector_cache = signals
        _sector_cache_date = today
        return signals

    except Exception as e:
        logger.warning("Sector rotation computation failed: %s", e)
        return []


def format_sector_csv(signals: list[dict]) -> str:
    """Format sector signals as CSV for Claude's prompt (~150 tokens)."""
    if not signals:
        return ""

    header = "etf,rs_trend,perf_1m%,perf_3m%,rsi14"
    rows = []
    for s in signals:
        perf_1m = f"+{s['perf_1m']}" if s['perf_1m'] >= 0 else str(s['perf_1m'])
        perf_3m = f"+{s['perf_3m']}" if s['perf_3m'] >= 0 else str(s['perf_3m'])
        rsi = str(s['rsi14']) if s['rsi14'] is not None else "NaN"
        rows.append(f"{s['etf']},{s['rs_trend']},{perf_1m},{perf_3m},{rsi}")

    return f"SECTOR ROTATION (vs SPY):\n{header}\n" + "\n".join(rows)
