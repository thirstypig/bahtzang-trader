"""Engine: P&L conversion + a synthetic end-to-end backtest run."""

from datetime import date, timedelta

import pandas as pd

from app.forex.engine import (
    Position,
    _evaluate_exit,
    quote_to_usd,
    run_backtest,
)
from app.forex.zones import Zone


def test_quote_to_usd_usd_quoted_pair_is_identity():
    assert quote_to_usd(100.0, "EURUSD", 1.10) == 100.0
    assert quote_to_usd(-50.0, "GBPUSD", 1.25) == -50.0


def test_quote_to_usd_usd_base_pair_divides_by_price():
    # USDJPY at 150: 1 JPY = 1/150 USD
    assert quote_to_usd(1500.0, "USDJPY", 150.0) == 10.0


def test_evaluate_exit_long_take_profit():
    zone = Zone(kind="support", top=1.10, bottom=1.05)
    pos = Position(
        symbol="EURUSD", direction="long", entry_date=date(2024, 1, 1),
        entry_price=1.06, stop_loss=1.0495, take_profit=1.0705,
        units=10000, zone=zone,
    )
    bar = pd.Series({"open": 1.06, "high": 1.075, "low": 1.058, "close": 1.07})
    price, reason = _evaluate_exit(pos, bar)
    assert reason == "take_profit"
    assert price == 1.0705


def test_evaluate_exit_long_stop_loss_first_when_both_hit():
    zone = Zone(kind="support", top=1.10, bottom=1.05)
    pos = Position(
        symbol="EURUSD", direction="long", entry_date=date(2024, 1, 1),
        entry_price=1.06, stop_loss=1.0495, take_profit=1.0705,
        units=10000, zone=zone,
    )
    bar = pd.Series({"open": 1.06, "high": 1.075, "low": 1.045, "close": 1.07})
    price, reason = _evaluate_exit(pos, bar)
    assert reason == "stop_loss"
    assert price == 1.0495


def test_evaluate_exit_zone_break_on_close():
    zone = Zone(kind="support", top=1.10, bottom=1.05)
    pos = Position(
        symbol="EURUSD", direction="long", entry_date=date(2024, 1, 1),
        entry_price=1.06, stop_loss=1.0445, take_profit=1.0755,
        units=10000, zone=zone,
    )
    # Close below zone.bottom (1.05) but above SL (1.0445) → zone break
    bar = pd.Series({"open": 1.06, "high": 1.062, "low": 1.046, "close": 1.048})
    price, reason = _evaluate_exit(pos, bar)
    assert reason == "zone_break"
    assert price == 1.048


def test_evaluate_exit_no_exit_when_bar_inside():
    zone = Zone(kind="support", top=1.10, bottom=1.05)
    pos = Position(
        symbol="EURUSD", direction="long", entry_date=date(2024, 1, 1),
        entry_price=1.06, stop_loss=1.0495, take_profit=1.0705,
        units=10000, zone=zone,
    )
    bar = pd.Series({"open": 1.06, "high": 1.065, "low": 1.055, "close": 1.062})
    price, reason = _evaluate_exit(pos, bar)
    assert price is None
    assert reason is None


def _build_synthetic_eurusd_bars() -> pd.DataFrame:
    """~150 daily bars: oscillating to seed pivots, then a clear support test+bounce."""
    rows = []
    d = date(2023, 1, 2)  # Monday
    # Phase 1: 100 daily bars oscillating between 1.10 and 1.20 to seed weekly pivots
    for i in range(100):
        # 10-day cycle: ramp up then down
        cycle = i % 10
        if cycle < 5:
            o = 1.10 + cycle * 0.02
            c = o + 0.01
        else:
            o = 1.20 - (cycle - 5) * 0.02
            c = o - 0.01
        h = max(o, c) + 0.005
        lo = min(o, c) - 0.005
        rows.append((d, o, h, lo, c))
        d += timedelta(days=1)

    # Phase 2: drop into the 1.10 support zone over ~10 bars
    for i in range(10):
        price = 1.18 - i * 0.009
        rows.append((d, price, price + 0.003, price - 0.003, price - 0.002))
        d += timedelta(days=1)

    # Phase 3: bullish pin bar at the support zone
    rows.append((d, 1.10, 1.105, 1.05, 1.10))  # body=0, this is doji — skip
    d += timedelta(days=1)
    # Use a real bullish pin: open=1.10, close=1.105 (body 0.005), low=1.07 (lower wick 0.03), high=1.106
    rows.append((d, 1.100, 1.106, 1.070, 1.105))
    d += timedelta(days=1)

    # Phase 4: rally to clear the TP
    for i in range(20):
        price = 1.105 + i * 0.005
        rows.append((d, price, price + 0.003, price - 0.001, price + 0.002))
        d += timedelta(days=1)

    return pd.DataFrame(rows, columns=["date", "open", "high", "low", "close"])


def test_run_backtest_smoke_and_structure():
    df = _build_synthetic_eurusd_bars()
    out = run_backtest(
        symbols=["EURUSD"],
        start=df["date"].iloc[0],
        end=df["date"].iloc[-1],
        initial_equity=10_000.0,
        risk_pct=0.02,
        sl_buffer_pct=0.001,
        pivot_lookback_weeks=100,
        cluster_pct=0.005,
        daily_data={"EURUSD": df},
    )
    # Structural checks — engine produced a coherent run
    assert out.equity_curve  # non-empty
    assert out.equity_curve[0]["date"] == str(df["date"].iloc[0])
    assert isinstance(out.total_trades, int)
    assert isinstance(out.win_rate_pct, float)
    # Final equity must be positive (no negative balances)
    assert out.final_equity > 0


def test_run_backtest_handles_empty_data_gracefully():
    out = run_backtest(
        symbols=["EURUSD"],
        start=date(2023, 1, 1),
        end=date(2023, 1, 31),
        daily_data={"EURUSD": pd.DataFrame(columns=["date", "open", "high", "low", "close"])},
    )
    assert out.total_trades == 0
    assert out.final_equity == 10_000.0
    assert out.equity_curve == []
