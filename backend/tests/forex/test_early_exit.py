"""Phase 1b: discretionary early-exit variants."""

from datetime import date

import pandas as pd
import pytest

from app.forex.engine import (
    Position,
    _evaluate_early_exit,
    _unrealized_r,
    run_backtest,
)
from app.forex.zones import Zone


def _make_long_pos(bars_open: int = 0) -> Position:
    return Position(
        symbol="EURUSD", direction="long", entry_date=date(2024, 1, 1),
        entry_price=1.10, stop_loss=1.09, take_profit=1.11,
        units=10000, zone=Zone(kind="support", top=1.10, bottom=1.09), bars_open=bars_open,
    )


def _make_short_pos(bars_open: int = 0) -> Position:
    return Position(
        symbol="EURUSD", direction="short", entry_date=date(2024, 1, 1),
        entry_price=1.10, stop_loss=1.11, take_profit=1.09,
        units=10000, zone=Zone(kind="resistance", top=1.10, bottom=1.09), bars_open=bars_open,
    )


def test_unrealized_r_long_units():
    pos = _make_long_pos()
    assert _unrealized_r(pos, 1.10) == 0.0
    assert _unrealized_r(pos, 1.11) == pytest.approx(1.0)
    assert _unrealized_r(pos, 1.09) == pytest.approx(-1.0)
    assert _unrealized_r(pos, 1.105) == pytest.approx(0.5)


def test_unrealized_r_short_units():
    pos = _make_short_pos()
    assert _unrealized_r(pos, 1.10) == 0.0
    assert _unrealized_r(pos, 1.09) == pytest.approx(1.0)
    assert _unrealized_r(pos, 1.11) == pytest.approx(-1.0)


def test_early_exit_disabled_when_mode_is_none():
    pos = _make_long_pos(bars_open=50)
    price, reason = _evaluate_early_exit(pos, 1.095, "none", 10, 0.3)
    assert price is None
    assert reason is None


def test_early_exit_respects_min_bars():
    pos = _make_long_pos(bars_open=5)  # below min
    price, reason = _evaluate_early_exit(pos, 1.095, "progress", 10, 0.3)
    assert price is None


def test_progress_mode_closes_meandering_trade():
    # 0.0R is below the 0.3R threshold → close
    pos = _make_long_pos(bars_open=15)
    price, reason = _evaluate_early_exit(pos, 1.10, "progress", 10, 0.3)
    assert reason == "early_exit_progress"
    assert price == 1.10


def test_progress_mode_lets_winners_run():
    # 0.5R is above 0.3R → keep
    pos = _make_long_pos(bars_open=15)
    price, reason = _evaluate_early_exit(pos, 1.105, "progress", 10, 0.3)
    assert price is None


def test_progress_mode_closes_losers():
    # -0.5R is below 0.3R → close (cuts losers early)
    pos = _make_long_pos(bars_open=15)
    price, reason = _evaluate_early_exit(pos, 1.095, "progress", 10, 0.3)
    assert reason == "early_exit_progress"


def test_time_band_mode_closes_meanderers_only():
    # Within ±0.3R band → close
    pos = _make_long_pos(bars_open=15)
    price, reason = _evaluate_early_exit(pos, 1.101, "time_band", 10, 0.3)
    assert reason == "early_exit_band"


def test_time_band_mode_keeps_committed_losers():
    # -0.5R is outside band → keep (let SL handle it)
    pos = _make_long_pos(bars_open=15)
    price, reason = _evaluate_early_exit(pos, 1.095, "time_band", 10, 0.3)
    assert price is None


def test_time_band_mode_keeps_committed_winners():
    pos = _make_long_pos(bars_open=15)
    price, reason = _evaluate_early_exit(pos, 1.105, "time_band", 10, 0.3)
    assert price is None


def test_run_backtest_invalid_mode_raises():
    with pytest.raises(ValueError):
        run_backtest(
            symbols=["EURUSD"], start=date(2024, 1, 1), end=date(2024, 1, 31),
            early_exit_mode="bogus",
            daily_data={"EURUSD": pd.DataFrame(columns=["date", "open", "high", "low", "close"])},
        )


def test_run_backtest_progress_mode_smoke():
    # Engine accepts the mode and runs without crashing on empty data.
    out = run_backtest(
        symbols=["EURUSD"], start=date(2024, 1, 1), end=date(2024, 1, 31),
        early_exit_mode="progress",
        early_exit_min_bars=5,
        early_exit_threshold_r=0.3,
        daily_data={"EURUSD": pd.DataFrame(columns=["date", "open", "high", "low", "close"])},
    )
    assert out.total_trades == 0
