"""Technical indicator computation with Alpaca Data API + pandas-ta.

Fetches daily OHLCV bars, computes RSI/MACD/BBands/SMA/ATR,
caches results daily, and formats as CSV for Claude's prompt.
"""

import asyncio
import logging
from datetime import date, timedelta

import pandas as pd
import pandas_ta as ta
from alpaca.data.historical import CryptoHistoricalDataClient, StockHistoricalDataClient
from alpaca.data.requests import CryptoBarsRequest, StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from app.config import settings
from app.symbols import is_crypto

logger = logging.getLogger(__name__)

# Module-level cache: recomputed once per trading day
_indicator_cache: dict[str, dict] = {}
_cache_date: date | None = None

# Lazy-init data clients (same credentials as trading client). Crypto bars
# MUST come from the crypto client — the stock client resolves "BTC" to a
# wrong equities instrument (the ~$35 phantom price bug).
_data_client: StockHistoricalDataClient | None = None
_crypto_client: CryptoHistoricalDataClient | None = None


def _get_data_client() -> StockHistoricalDataClient:
    global _data_client
    if _data_client is None:
        _data_client = StockHistoricalDataClient(
            settings.ALPACA_API_KEY, settings.ALPACA_SECRET_KEY
        )
    return _data_client


def _get_crypto_client() -> CryptoHistoricalDataClient:
    global _crypto_client
    if _crypto_client is None:
        _crypto_client = CryptoHistoricalDataClient(
            settings.ALPACA_API_KEY, settings.ALPACA_SECRET_KEY
        )
    return _crypto_client


async def _fetch_daily_bars(
    tickers: list[str], lookback_days: int = 365
) -> pd.DataFrame:
    """Fetch daily OHLCV bars from Alpaca for multiple tickers in one call."""
    client = _get_data_client()
    end = date.today()
    start = end - timedelta(days=lookback_days)

    request = StockBarsRequest(
        symbol_or_symbols=tickers,
        timeframe=TimeFrame.Day,
        start=start,
        end=end,
    )
    bars = await asyncio.to_thread(client.get_stock_bars, request)
    return bars.df


async def _fetch_daily_crypto_bars(
    tickers: list[str], lookback_days: int = 365
) -> pd.DataFrame:
    """Fetch daily OHLCV bars for crypto pairs via the crypto data client."""
    client = _get_crypto_client()
    end = date.today()
    start = end - timedelta(days=lookback_days)

    request = CryptoBarsRequest(
        symbol_or_symbols=tickers,
        timeframe=TimeFrame.Day,
        start=start,
        end=end,
    )
    bars = await asyncio.to_thread(client.get_crypto_bars, request)
    return bars.df


def _validate_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """Clean and validate OHLCV data before indicator computation."""
    df = df[df["close"] > 0]
    df = df[~df.index.duplicated(keep="last")]
    df = df.ffill(limit=5)
    df = df.sort_index()
    return df


def _compute_indicators(df: pd.DataFrame) -> dict:
    """Compute all indicator groups for a single ticker's OHLCV DataFrame."""
    if len(df) < 14:
        return {}

    # Compute indicators
    rsi = df.ta.rsi(length=14)
    macd = df.ta.macd(fast=12, slow=26, signal=9)
    bbands = df.ta.bbands(length=20, std=2)
    sma50 = df.ta.sma(length=50)
    sma200 = df.ta.sma(length=200)
    atr = df.ta.atr(length=14)

    latest = df.iloc[-1]

    result = {
        "price": round(float(latest["close"]), 2),
        "rsi14": round(float(rsi.iloc[-1]), 1) if rsi is not None and not rsi.empty else None,
    }

    # MACD
    if macd is not None and not macd.empty:
        macd_cols = macd.columns.tolist()
        result["macd"] = round(float(macd[macd_cols[0]].iloc[-1]), 2)
        result["macd_sig"] = round(float(macd[macd_cols[1]].iloc[-1]), 2)
    else:
        result["macd"] = None
        result["macd_sig"] = None

    # Bollinger Bands
    if bbands is not None and not bbands.empty:
        bb_cols = bbands.columns.tolist()
        result["bb_lower"] = round(float(bbands[bb_cols[0]].iloc[-1]), 2)
        result["bb_mid"] = round(float(bbands[bb_cols[1]].iloc[-1]), 2)
        result["bb_upper"] = round(float(bbands[bb_cols[2]].iloc[-1]), 2)
    else:
        result["bb_lower"] = None
        result["bb_mid"] = None
        result["bb_upper"] = None

    # SMAs
    result["sma50"] = round(float(sma50.iloc[-1]), 2) if sma50 is not None and not sma50.empty and len(df) >= 50 else None
    result["sma200"] = round(float(sma200.iloc[-1]), 2) if sma200 is not None and not sma200.empty and len(df) >= 200 else None

    # ATR
    result["atr14"] = round(float(atr.iloc[-1]), 2) if atr is not None and not atr.empty else None

    return result


async def get_indicators(tickers: list[str]) -> dict[str, dict]:
    """Return cached indicators, recomputing only if stale (new trading day)."""
    global _indicator_cache, _cache_date

    today = date.today()
    if _cache_date == today and all(t in _indicator_cache for t in tickers):
        return {t: _indicator_cache[t] for t in tickers if t in _indicator_cache}

    if not tickers:
        return {}

    logger.info("Computing technical indicators for %d tickers", len(tickers))

    # Stocks and crypto come from different Alpaca data clients. Fetch each
    # group independently so a failure in one can't blank the other's
    # indicators for the cycle.
    stock_tickers = [t for t in tickers if not is_crypto(t)]
    crypto_tickers = [t for t in tickers if is_crypto(t)]

    groups: list[tuple[list[str], pd.DataFrame]] = []
    if stock_tickers:
        try:
            groups.append((stock_tickers, await _fetch_daily_bars(stock_tickers, lookback_days=365)))
        except Exception as e:
            logger.warning("Failed to fetch stock OHLCV data: %s", e)
    if crypto_tickers:
        try:
            groups.append((crypto_tickers, await _fetch_daily_crypto_bars(crypto_tickers, lookback_days=365)))
        except Exception as e:
            logger.warning("Failed to fetch crypto OHLCV data: %s", e)

    if not groups:
        return {}

    results = {}
    for group, bars_df in groups:
        if bars_df is None or bars_df.empty:
            continue
        for ticker in group:
            try:
                if ticker in bars_df.index.get_level_values(0):
                    ticker_df = bars_df.loc[ticker].copy()
                    ticker_df = _validate_ohlcv(ticker_df)
                    indicators = _compute_indicators(ticker_df)
                    if indicators:
                        results[ticker] = indicators
                        _indicator_cache[ticker] = indicators
            except Exception as e:
                logger.warning("Failed to compute indicators for %s: %s", ticker, e)

    _cache_date = today
    return results


def format_indicators_csv(indicators: dict[str, dict]) -> str:
    """Format indicators as CSV for Claude's prompt (~400 tokens for 20 stocks)."""
    if not indicators:
        return ""

    header = "ticker,price,rsi14,macd,macd_sig,bb_upper,bb_lower,sma50,sma200,atr14"
    rows = []
    for ticker, ind in sorted(indicators.items()):
        def fmt(v):
            return str(v) if v is not None else "NaN"

        rows.append(
            f"{ticker},{fmt(ind.get('price'))},{fmt(ind.get('rsi14'))},"
            f"{fmt(ind.get('macd'))},{fmt(ind.get('macd_sig'))},"
            f"{fmt(ind.get('bb_upper'))},{fmt(ind.get('bb_lower'))},"
            f"{fmt(ind.get('sma50'))},{fmt(ind.get('sma200'))},{fmt(ind.get('atr14'))}"
        )

    return f"TECHNICALS (daily):\n{header}\n" + "\n".join(rows)
