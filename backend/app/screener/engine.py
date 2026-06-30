"""Screener ranking engine.

Pure factor math (rank_universe) + an IO orchestrator (run_screener). The ranker
scores each name on momentum, relative strength vs SPY, trend, and volatility,
then combines them as cross-sectional z-scores so the universe is ranked relative
to itself each day.
"""

import logging
from datetime import date, timedelta

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Lookback windows in trading days (~21/mo)
_W3, _W6, _W12 = 63, 126, 252
MIN_BARS = 253          # need the full 12-month window so momentum is comparable across names
MAX_VOLATILITY = 1.5    # hard-exclude annualized vol above this (broken/meme)
# Liquidity floor: median daily dollar volume over the last 3 months. A small
# account still needs tight spreads — thin names eat market-order fills. $20M/day
# comfortably covers everything in the S&P 500/400 worth trading and quietly
# drops anything in the mid-cap extension that has gone illiquid or stale.
MIN_DOLLAR_VOLUME = 20_000_000
DEFAULT_TOP_N = 40
FETCH_CALENDAR_DAYS = 400  # ~280 trading days → enough for the 252d window

# Composite weights — momentum-led, trend-aware, volatility-penalized.
W_MOMENTUM, W_REL_STRENGTH, W_TREND, W_VOL = 0.40, 0.30, 0.20, 0.10

BENCHMARK = "SPY"


def _total_return(closes: pd.Series, window: int) -> float | None:
    if len(closes) <= window:
        return None
    past = closes.iloc[-window - 1]
    if past <= 0:
        return None
    return float(closes.iloc[-1] / past - 1.0)


def _rsi(closes: pd.Series, period: int = 14) -> float:
    if len(closes) <= period:
        return 50.0
    delta = closes.diff().dropna()
    gains = delta.clip(lower=0).rolling(period).mean().iloc[-1]
    losses = (-delta.clip(upper=0)).rolling(period).mean().iloc[-1]
    if losses == 0:
        return 100.0 if gains > 0 else 50.0
    rs = gains / losses
    return float(100.0 - 100.0 / (1.0 + rs))


def _momentum(closes: pd.Series) -> float | None:
    """Average of the computable 3/6/12-month total returns."""
    windows = [_total_return(closes, w) for w in (_W3, _W6, _W12)]
    vals = [r for r in windows if r is not None]
    return float(np.mean(vals)) if vals else None


def _trend_score(closes: pd.Series) -> float:
    """0..1: above 50d SMA = 0.5, 50d above 200d SMA = 0.5."""
    price = closes.iloc[-1]
    sma50 = closes.iloc[-50:].mean() if len(closes) >= 50 else closes.mean()
    sma200 = closes.iloc[-200:].mean() if len(closes) >= 200 else closes.mean()
    return float((price > sma50) * 0.5 + (sma50 > sma200) * 0.5)


def _volatility(closes: pd.Series, window: int = _W3) -> float:
    rets = closes.pct_change().dropna().iloc[-window:]
    if len(rets) < 2:
        return 0.0
    return float(rets.std() * np.sqrt(252))


def _median_dollar_volume(df: pd.DataFrame, window: int = _W3) -> float:
    """Median of close × volume over the trailing window."""
    if "volume" not in df or "close" not in df:
        return 0.0
    dollar = (df["close"].astype(float) * df["volume"].astype(float)).iloc[-window:]
    return float(dollar.median()) if len(dollar) else 0.0


def _compute_factors(df: pd.DataFrame, spy_closes: pd.Series | None) -> dict | None:
    """Per-ticker factor dict, or None if there isn't enough history or liquidity."""
    if df is None or len(df) < MIN_BARS or "close" not in df:
        return None
    if _median_dollar_volume(df) < MIN_DOLLAR_VOLUME:
        return None
    closes = df["close"].astype(float)

    momentum = _momentum(closes)
    if momentum is None:
        return None

    # Relative strength vs SPY over the longest window both cover.
    rel_strength = momentum
    if spy_closes is not None and len(spy_closes) >= MIN_BARS:
        for w in (_W6, _W3):
            stock_r, spy_r = _total_return(closes, w), _total_return(spy_closes, w)
            if stock_r is not None and spy_r is not None:
                rel_strength = stock_r - spy_r
                break

    return {
        "momentum": momentum,
        "rel_strength": rel_strength,
        "trend_score": _trend_score(closes),
        "rsi": _rsi(closes),
        "volatility": _volatility(closes),
        "price": float(closes.iloc[-1]),
    }


def _zscores(values: list[float]) -> list[float]:
    arr = np.array(values, dtype=float)
    std = arr.std()
    if std == 0:
        return [0.0] * len(arr)
    # Coerce to native floats: np.float64 is a float subclass that SQLite
    # accepts but PostgreSQL rejects (numpy 2.x repr 'np.float64(...)' lands in
    # the SQL as a `np.` schema reference). composite_score is built from these.
    return [float(x) for x in (arr - arr.mean()) / std]


def rank_universe(
    bars: dict[str, pd.DataFrame],
    top_n: int = DEFAULT_TOP_N,
) -> list[dict]:
    """Score and rank a universe of {ticker: OHLCV DataFrame}.

    Returns up to top_n candidate dicts sorted by composite_score desc, each with
    its rank (1-based) and raw factor values. Pure function — no IO.
    """
    spy_closes = (
        bars[BENCHMARK]["close"].astype(float)
        if BENCHMARK in bars and "close" in bars[BENCHMARK]
        else None
    )

    scored: dict[str, dict] = {}
    for ticker, df in bars.items():
        factors = _compute_factors(df, spy_closes)
        if factors is None or factors["volatility"] > MAX_VOLATILITY:
            continue
        scored[ticker] = factors

    if not scored:
        return []

    tickers = list(scored.keys())
    z_mom = _zscores([scored[t]["momentum"] for t in tickers])
    z_rel = _zscores([scored[t]["rel_strength"] for t in tickers])
    z_vol = _zscores([scored[t]["volatility"] for t in tickers])
    # z-score trend too, so its weight is comparable to the other factors
    # (raw trend_score is bounded 0..1 while z-scores swing ~±3, which would
    # otherwise leave trend ~5-10x underweighted vs its nominal W_TREND).
    z_trend = _zscores([scored[t]["trend_score"] for t in tickers])

    ranked: list[dict] = []
    for i, t in enumerate(tickers):
        f = scored[t]
        composite = (
            W_MOMENTUM * z_mom[i]
            + W_REL_STRENGTH * z_rel[i]
            + W_TREND * z_trend[i]
            - W_VOL * z_vol[i]
        )
        ranked.append({"ticker": t, "composite_score": composite, **f})

    ranked.sort(key=lambda r: r["composite_score"], reverse=True)
    ranked = ranked[:top_n]
    for rank, row in enumerate(ranked, start=1):
        row["rank"] = rank
    return ranked


async def run_screener(
    db: Session,
    universe: list[str] | None = None,
    top_n: int = DEFAULT_TOP_N,
) -> "object":
    """Fetch bars, rank the universe, and persist a ScreenerRun + candidates.

    Returns the completed ScreenerRun. IO-heavy: caches OHLCV via the shared
    backtest data pipeline (gap-fill, so repeat runs are cheap).
    """
    from app.screener.models import ScreenerRun, ScreenerCandidate
    from app.screener.universe import SCREENER_UNIVERSE
    from app.backtest.data import fetch_and_cache_bars, load_bars

    tickers = list(dict.fromkeys((universe or SCREENER_UNIVERSE) + [BENCHMARK]))

    run = ScreenerRun(universe_size=len(tickers), status="running")
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        today = date.today()
        start = today - timedelta(days=FETCH_CALENDAR_DAYS)
        await fetch_and_cache_bars(tickers, start, today, db)
        bars = load_bars(tickers, start, today, db)

        ranked = rank_universe(bars, top_n=top_n)

        for row in ranked:
            db.add(ScreenerCandidate(
                run_id=run.id,
                rank=row["rank"],
                ticker=row["ticker"],
                composite_score=row["composite_score"],
                momentum=row["momentum"],
                rel_strength=row["rel_strength"],
                trend_score=row["trend_score"],
                rsi=row["rsi"],
                volatility=row["volatility"],
                price=row["price"],
            ))
        run.scored_count = len(ranked)
        run.status = "complete"
        db.commit()
        db.refresh(run)
        logger.info("Screener run %d complete: %d candidates from %d names",
                    run.id, len(ranked), len(tickers))
    except Exception as e:
        logger.exception("Screener run %d failed: %s", run.id, e)
        run.status = "failed"
        run.error = str(e)[:500]
        db.commit()

    return run


def latest_top_tickers(db: Session, top_n: int) -> list[str]:
    """Top-N tickers from the most recent COMPLETE screener run, rank order.

    This is the screener→portfolio feed: a portfolio opts in by setting
    strategy_params["screener_top_n"] and these names join its candidate
    universe each cycle. Empty list when no complete run exists (screener
    failure must never block a trading cycle).
    """
    from app.screener.models import ScreenerRun, ScreenerCandidate

    run = (
        db.query(ScreenerRun)
        .filter(ScreenerRun.status == "complete")
        .order_by(ScreenerRun.run_at.desc())
        .first()
    )
    if not run:
        return []
    rows = (
        db.query(ScreenerCandidate.ticker)
        .filter(ScreenerCandidate.run_id == run.id, ScreenerCandidate.rank <= top_n)
        .order_by(ScreenerCandidate.rank)
        .all()
    )
    return [r.ticker for r in rows]


def format_screener_csv(db: Session, top_n: int) -> str:
    """CSV block of the latest run's top-N for the Claude prompt.

    The ranking context is the point — without the scores these names would
    be indistinguishable from ordinary watchlist tickers in the prompt.
    """
    from app.screener.models import ScreenerRun, ScreenerCandidate

    run = (
        db.query(ScreenerRun)
        .filter(ScreenerRun.status == "complete")
        .order_by(ScreenerRun.run_at.desc())
        .first()
    )
    if not run:
        return ""
    rows = (
        db.query(ScreenerCandidate)
        .filter(ScreenerCandidate.run_id == run.id, ScreenerCandidate.rank <= top_n)
        .order_by(ScreenerCandidate.rank)
        .all()
    )
    if not rows:
        return ""
    lines = [
        "SCREENER TOP CANDIDATES (daily quantitative ranking of ~650 US large/mid-caps "
        "by momentum + relative strength vs SPY + trend, volatility-penalized; "
        "rank 1 = strongest) — rank,ticker,composite,momentum,vs_spy,trend,rsi,ann_vol:",
    ]
    for c in rows:
        lines.append(
            f"{c.rank},{c.ticker},{c.composite_score:.2f},{c.momentum:+.1%},"
            f"{c.rel_strength:+.1%},{c.trend_score:.1f},{c.rsi:.0f},{c.volatility:.0%}"
        )
    return "\n".join(lines)
