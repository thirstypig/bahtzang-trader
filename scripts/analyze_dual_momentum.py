#!/usr/bin/env python3
"""
Dual Momentum backtest analysis — runs 4 historical windows and prints metrics.

Fetches real adjusted prices from yfinance; no Alpaca or DB required.
Run with the backend venv:
  backend/venv/bin/python scripts/analyze_dual_momentum.py
"""

import os
import sys
import math
from datetime import date
from collections import defaultdict
from unittest.mock import MagicMock

# --- Stub heavy native deps BEFORE any app import touches them ---
for _m in ("numba", "pandas_ta", "pandas_ta.utils", "pandas_ta.utils._math"):
    if _m not in sys.modules:
        sys.modules[_m] = MagicMock()

os.environ.setdefault("ANTHROPIC_API_KEY", "dummy")
os.environ.setdefault("ALPHA_VANTAGE_KEY", "dummy")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("ALLOWED_EMAIL", "test@example.com")
os.environ.setdefault("ALPACA_API_KEY", "dummy")
os.environ.setdefault("ALPACA_SECRET_KEY", "dummy")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pandas as pd
import yfinance as yf

from app.analytics import compute_metrics
from app.backtest.strategies import (
    DualMomentum, BuyAndHold, SMACrossover,
    SimulationState, PositionInfo,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TICKERS = ["SPY", "VEU", "BIL"]
INITIAL = 100_000.0

WINDOWS = [
    ("Long 2005–2025",          date(2005, 1,  1), date(2025, 4, 30)),
    ("Recent decade 2015–2025", date(2015, 1,  1), date(2025, 4, 30)),
    ("2008 stress 2007–2010",   date(2007, 1,  1), date(2010, 12, 31)),
    ("COVID stress 2019–2021",  date(2019, 1,  1), date(2021, 12, 31)),
]

# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def fetch_all(tickers: list[str], fetch_start: date, fetch_end: date) -> dict[str, pd.DataFrame]:
    """Download adjusted close prices from yfinance for all tickers."""
    bars: dict[str, pd.DataFrame] = {}
    for ticker in tickers:
        try:
            t = yf.Ticker(ticker)
            hist = t.history(start=fetch_start, end=fetch_end, auto_adjust=True)
            if hist.empty:
                print(f"  WARNING: No data returned for {ticker}")
                continue
            # Strip timezone, lowercase column, clean index
            hist.index = hist.index.tz_localize(None)
            df = pd.DataFrame({"close": hist["Close"].astype(float)}, index=hist.index)
            bars[ticker] = df
            print(f"  {ticker}: {df.index[0].date()} → {df.index[-1].date()}  ({len(df):,} bars)")
        except Exception as exc:
            print(f"  ERROR fetching {ticker}: {exc}")
    return bars

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def trading_days_in(bars: dict, start: date, end: date) -> list[date]:
    all_dates: set[date] = set()
    for df in bars.values():
        for ts in df.index:
            d = ts.date() if hasattr(ts, "date") else ts
            if start <= d <= end:
                all_dates.add(d)
    return sorted(all_dates)


def mark_to_market(state: SimulationState, bars_sf: dict) -> float:
    total = state.cash
    for ticker, pos in state.positions.items():
        if ticker in bars_sf and not bars_sf[ticker].empty:
            total += pos.quantity * float(bars_sf[ticker].iloc[-1]["close"])
    return total


def is_month_end(d: date) -> bool:
    nxt = (pd.Timestamp(d) + pd.offsets.BusinessDay(1)).date()
    return nxt.month != d.month


def cagr_pct(total_return_pct: float, start: date, end: date) -> float:
    years = (end - start).days / 365.25
    if years <= 0 or total_return_pct <= -100:
        return float("nan")
    return ((1 + total_return_pct / 100) ** (1.0 / years) - 1) * 100


def rsi(closes: pd.Series, period: int = 14) -> float | None:
    """Simple Wilder RSI — used to feed RSIMeanReversion without pandas_ta."""
    if len(closes) < period + 1:
        return None
    delta = closes.diff().dropna()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean().iloc[-1]
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean().iloc[-1]
    if loss == 0:
        return 100.0
    return 100.0 - 100.0 / (1.0 + gain / loss)

# ---------------------------------------------------------------------------
# Strategy runners
# ---------------------------------------------------------------------------

def run_dual_momentum(bars: dict, start: date, end: date) -> dict:
    """DualMomentum: 100 % single-position, no stop-loss."""
    strategy = DualMomentum()
    params = {"lookback_months": 12, "us_ticker": "SPY", "intl_ticker": "VEU", "defensive_ticker": "BIL"}

    state = SimulationState(cash=INITIAL)
    asset_days: dict[str, int] = defaultdict(int)
    equity_curve: list[float] = []
    n_trades = 0

    for d in trading_days_in(bars, start, end):
        ts = pd.Timestamp(d)
        sf = {t: df[df.index <= ts] for t, df in bars.items() if not df[df.index <= ts].empty}

        for sig in strategy.decide(d, {}, state, sf, params):
            t, price = sig.ticker, float(sf[sig.ticker].iloc[-1]["close"]) if sig.ticker in sf else None
            if price is None:
                continue
            if sig.action == "sell" and t in state.positions:
                pos = state.positions.pop(t)
                state.cash += pos.quantity * price
                n_trades += 1
            elif sig.action == "buy" and t not in state.positions:
                equity = mark_to_market(state, sf)
                qty = int(equity * 0.995 / price)
                if qty > 0:
                    state.cash -= qty * price
                    state.positions[t] = PositionInfo(quantity=qty, avg_price=price)
                    n_trades += 1

        held = list(state.positions.keys())
        asset_days[held[0] if held else "CASH"] += 1
        equity_curve.append(mark_to_market(state, sf))

    total_days = len(equity_curve)
    asset_pct = {k: round(v / total_days * 100, 1) for k, v in asset_days.items()} if total_days else {}

    m = compute_metrics(equity_curve)
    return _result("Dual Momentum", m, n_trades, start, end, asset_pct=asset_pct)


def run_spy_bah(bars: dict, start: date, end: date) -> dict:
    """100 % SPY buy-and-hold benchmark."""
    state = SimulationState(cash=INITIAL)
    equity_curve: list[float] = []
    spy_qty = 0
    bought = False

    for d in trading_days_in(bars, start, end):
        ts = pd.Timestamp(d)
        sf = {t: df[df.index <= ts] for t, df in bars.items() if not df[df.index <= ts].empty}
        if "SPY" not in sf:
            continue
        price = float(sf["SPY"].iloc[-1]["close"])
        if not bought:
            spy_qty = int(state.cash * 0.995 / price)
            state.cash -= spy_qty * price
            state.positions["SPY"] = PositionInfo(quantity=spy_qty, avg_price=price)
            bought = True
        equity_curve.append(state.cash + spy_qty * price)

    m = compute_metrics(equity_curve)
    return _result("SPY Buy-and-Hold", m, 1, start, end, asset_pct={"SPY": 100.0})


def run_60_40(bars: dict, start: date, end: date) -> dict:
    """60 % SPY / 40 % BIL, monthly rebalance."""
    state = SimulationState(cash=INITIAL)
    equity_curve: list[float] = []
    spy_qty = bil_qty = 0
    n_trades = 0
    initialized = False
    last_rebal_month: int | None = None

    for d in trading_days_in(bars, start, end):
        ts = pd.Timestamp(d)
        sf = {t: df[df.index <= ts] for t, df in bars.items() if not df[df.index <= ts].empty}
        if "SPY" not in sf or "BIL" not in sf:
            continue
        sp = float(sf["SPY"].iloc[-1]["close"])
        bp = float(sf["BIL"].iloc[-1]["close"])

        if not initialized:
            spy_qty = int(INITIAL * 0.60 / sp)
            bil_qty = int(INITIAL * 0.40 / bp)
            state.cash = INITIAL - spy_qty * sp - bil_qty * bp
            initialized = True
            n_trades += 2
        elif is_month_end(d) and d.month != last_rebal_month:
            last_rebal_month = d.month
            total = state.cash + spy_qty * sp + bil_qty * bp
            new_spy = int(total * 0.60 / sp)
            new_bil = int(total * 0.40 / bp)
            state.cash += (spy_qty - new_spy) * sp + (bil_qty - new_bil) * bp
            spy_qty, bil_qty = new_spy, new_bil
            n_trades += 2

        equity_curve.append(state.cash + spy_qty * sp + bil_qty * bp)

    m = compute_metrics(equity_curve)
    return _result("60/40 SPY/BIL", m, n_trades, start, end, asset_pct={"SPY": 60.0, "BIL": 40.0})


def run_sma_crossover(bars: dict, start: date, end: date) -> dict:
    """SMA Crossover (50/200) on SPY/VEU/BIL — max 33 % per position, 5 % stop-loss."""
    strategy = SMACrossover()
    params = {"fast_period": 50, "slow_period": 200}
    state = SimulationState(cash=INITIAL)
    equity_curve: list[float] = []
    n_trades = 0
    MAX_POS_PCT = 0.33
    STOP = 0.05

    for d in trading_days_in(bars, start, end):
        ts = pd.Timestamp(d)
        sf = {t: df[df.index <= ts] for t, df in bars.items() if not df[df.index <= ts].empty}

        equity = mark_to_market(state, sf)
        for sig in strategy.decide(d, {}, state, sf, params):
            if sig.ticker not in sf:
                continue
            price = float(sf[sig.ticker].iloc[-1]["close"])
            if sig.action == "buy" and sig.ticker not in state.positions:
                alloc = min(equity * MAX_POS_PCT, state.cash * 0.95)
                qty = int(alloc / price)
                if qty > 0 and len(state.positions) < 3:
                    state.cash -= qty * price
                    state.positions[sig.ticker] = PositionInfo(quantity=qty, avg_price=price)
                    n_trades += 1
            elif sig.action == "sell" and sig.ticker in state.positions:
                pos = state.positions.pop(sig.ticker)
                state.cash += pos.quantity * price
                n_trades += 1

        for t in list(state.positions.keys()):
            if t not in sf:
                continue
            price = float(sf[t].iloc[-1]["close"])
            pos = state.positions[t]
            if (price - pos.avg_price) / pos.avg_price <= -STOP:
                state.cash += pos.quantity * price
                del state.positions[t]
                n_trades += 1

        equity_curve.append(mark_to_market(state, sf))

    m = compute_metrics(equity_curve)
    return _result("SMA Crossover", m, n_trades, start, end)


def run_rsi_mean_reversion(bars: dict, start: date, end: date) -> dict:
    """RSI Mean Reversion on SPY/VEU/BIL — RSI computed without pandas_ta."""
    state = SimulationState(cash=INITIAL)
    equity_curve: list[float] = []
    n_trades = 0
    OVERSOLD = 30
    OVERBOUGHT = 70
    MAX_POS_PCT = 0.33
    STOP = 0.05

    for d in trading_days_in(bars, start, end):
        ts = pd.Timestamp(d)
        sf = {t: df[df.index <= ts] for t, df in bars.items() if not df[df.index <= ts].empty}

        equity = mark_to_market(state, sf)

        for ticker, df_t in sf.items():
            rsi_val = rsi(df_t["close"])
            if rsi_val is None:
                continue
            price = float(df_t.iloc[-1]["close"])

            if rsi_val < OVERSOLD and ticker not in state.positions:
                alloc = min(equity * MAX_POS_PCT, state.cash * 0.95)
                qty = int(alloc / price)
                if qty > 0 and len(state.positions) < 3:
                    state.cash -= qty * price
                    state.positions[ticker] = PositionInfo(quantity=qty, avg_price=price)
                    n_trades += 1
            elif rsi_val > OVERBOUGHT and ticker in state.positions:
                pos = state.positions.pop(ticker)
                state.cash += pos.quantity * price
                n_trades += 1

        for t in list(state.positions.keys()):
            if t not in sf:
                continue
            price = float(sf[t].iloc[-1]["close"])
            pos = state.positions[t]
            if (price - pos.avg_price) / pos.avg_price <= -STOP:
                state.cash += pos.quantity * price
                del state.positions[t]
                n_trades += 1

        equity_curve.append(mark_to_market(state, sf))

    m = compute_metrics(equity_curve)
    return _result("RSI Mean Reversion", m, n_trades, start, end)


def _result(name, m, n_trades, start, end, asset_pct=None) -> dict:
    return {
        "name": name,
        "total_return": m.total_return_pct,
        "cagr": cagr_pct(m.total_return_pct, start, end),
        "sharpe": m.sharpe_ratio,
        "sortino": m.sortino_ratio,
        "max_dd": m.max_drawdown_pct,
        "win_rate": m.win_rate_pct,
        "profit_factor": m.profit_factor,
        "vol": m.volatility_annual_pct,
        "n_trades": n_trades,
        "asset_pct": asset_pct or {},
        "num_days": m.num_trading_days,
    }

# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def pf(v, decimals=1):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "N/A"
    return f"{v:.{decimals}f}"


def pp(v, decimals=1):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "N/A"
    return f"{v:+.{decimals}f}%"


def print_window(label: str, results: list[dict]) -> None:
    print(f"\n{'═'*82}")
    print(f"  {label}")
    print(f"{'═'*82}")
    hdr = f"{'Strategy':<22} {'CAGR':>7} {'TotalRet':>9} {'Sharpe':>7} {'Sortino':>8} {'MaxDD':>8} {'Trades':>7} {'Vol':>7}"
    print(hdr)
    print("-" * 82)
    for r in results:
        print(
            f"{r['name']:<22} "
            f"{pp(r['cagr']):>7} "
            f"{pp(r['total_return']):>9} "
            f"{pf(r['sharpe'], 2):>7} "
            f"{pf(r['sortino'], 2):>8} "
            f"{pp(r['max_dd']):>8} "
            f"{r['n_trades']:>7} "
            f"{pf(r['vol']):>7}"
        )

    # DualMomentum asset time
    dm = next((r for r in results if r["name"] == "Dual Momentum"), None)
    if dm and dm["asset_pct"]:
        parts = "  |  ".join(f"{k}: {v:.0f}%" for k, v in sorted(dm["asset_pct"].items()))
        print(f"\n  DM asset time: {parts}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("  Dual Momentum Backtest Analysis")
    print("=" * 60)
    print("\nFetching historical data from yfinance...")

    # Fetch broad range once (covers warm-up for all windows)
    all_bars = fetch_all(TICKERS, date(2003, 6, 1), date(2025, 5, 10))

    if len(all_bars) < 3:
        print("ERROR: Could not fetch all required tickers. Aborting.")
        sys.exit(1)

    all_results: dict[str, list[dict]] = {}

    for label, start, end in WINDOWS:
        print(f"\n--- Running: {label} ---")
        window_bars = {t: df for t, df in all_bars.items()}
        res = [
            run_dual_momentum(window_bars, start, end),
            run_spy_bah(window_bars, start, end),
            run_60_40(window_bars, start, end),
            run_sma_crossover(window_bars, start, end),
            run_rsi_mean_reversion(window_bars, start, end),
        ]
        all_results[label] = res
        print_window(label, res)

    # CSV dump for memo
    print("\n\n--- RAW CSV (copy for memo) ---")
    print("window,strategy,cagr,total_return,sharpe,sortino,max_dd,n_trades,vol,spy_pct,veu_pct,bil_pct,cash_pct")
    for label, res_list in all_results.items():
        for r in res_list:
            ap = r["asset_pct"]
            print(
                f"{label},{r['name']},"
                f"{pf(r['cagr'])},"
                f"{pf(r['total_return'])},"
                f"{pf(r['sharpe'],2)},"
                f"{pf(r['sortino'],2)},"
                f"{pf(r['max_dd'])},"
                f"{r['n_trades']},"
                f"{pf(r['vol'])},"
                f"{ap.get('SPY',0)},"
                f"{ap.get('VEU',0)},"
                f"{ap.get('BIL',0)},"
                f"{ap.get('CASH',0)}"
            )
