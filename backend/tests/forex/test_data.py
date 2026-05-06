"""Forex data layer: yfinance cache logic + weekly resample.

These tests cover behavior the buddy implicitly depends on when running
parameter-sweep backtests:
  - cache hits don't fan out to yfinance (otherwise his quota dies)
  - cache misses upsert (otherwise every run re-fetches)
  - weekly resample produces correctly-aggregated OHLC bars
"""

from datetime import date, timedelta
from unittest.mock import patch

import pandas as pd

from app.forex.data import fetch_daily_bars, resample_to_weekly
from app.forex.models import ForexBar


# ---------------------------------------------------------------------------
# resample_to_weekly — pure function, no I/O
# ---------------------------------------------------------------------------


def _daily_df(rows):
    return pd.DataFrame(rows, columns=["date", "open", "high", "low", "close"])


def test_resample_empty_input_returns_empty():
    out = resample_to_weekly(_daily_df([]))
    assert out.empty


def test_resample_one_week_aggregates_ohlc():
    # Mon..Fri 2024-01-01 = Mon, 2024-01-05 = Fri
    rows = [
        (date(2024, 1, 1), 1.10, 1.12, 1.09, 1.11),
        (date(2024, 1, 2), 1.11, 1.13, 1.10, 1.12),
        (date(2024, 1, 3), 1.12, 1.15, 1.11, 1.14),  # week high
        (date(2024, 1, 4), 1.14, 1.14, 1.08, 1.09),  # week low
        (date(2024, 1, 5), 1.09, 1.11, 1.08, 1.10),  # Friday close
    ]
    out = resample_to_weekly(_daily_df(rows))
    assert len(out) == 1
    bar = out.iloc[0]
    assert bar["open"] == 1.10  # Monday open
    assert bar["high"] == 1.15  # max across week
    assert bar["low"] == 1.08   # min across week
    assert bar["close"] == 1.10  # Friday close


def test_resample_two_weeks_produces_two_bars():
    rows = []
    # Week 1: Mon-Fri 2024-01-01..05
    for i, day in enumerate(pd.bdate_range("2024-01-01", "2024-01-05").date):
        rows.append((day, 1.10 + i * 0.01, 1.11 + i * 0.01, 1.09 + i * 0.01, 1.10 + i * 0.01))
    # Week 2: Mon-Fri 2024-01-08..12
    for i, day in enumerate(pd.bdate_range("2024-01-08", "2024-01-12").date):
        rows.append((day, 1.20 + i * 0.01, 1.21 + i * 0.01, 1.19 + i * 0.01, 1.20 + i * 0.01))

    out = resample_to_weekly(_daily_df(rows))
    assert len(out) == 2
    assert out.iloc[0]["close"] < out.iloc[1]["open"]  # week 2 starts higher


# ---------------------------------------------------------------------------
# fetch_daily_bars — DB cache + yfinance fallback
# ---------------------------------------------------------------------------


def _mk_yf_df(start: date, days: int) -> pd.DataFrame:
    """Synthetic yfinance-shaped output."""
    rows = []
    for i in range(days):
        d = start + timedelta(days=i)
        if d.weekday() >= 5:  # skip weekends (yfinance does the same)
            continue
        rows.append((d, 1.10, 1.11, 1.09, 1.10))
    return pd.DataFrame(rows, columns=["date", "open", "high", "low", "close"])


def test_fetch_no_db_bypasses_cache_and_calls_yfinance():
    fake = _mk_yf_df(date(2024, 1, 1), 7)
    with patch("app.forex.data._yf_fetch", return_value=fake) as m:
        out = fetch_daily_bars("EURUSD", date(2024, 1, 1), date(2024, 1, 7), db=None)
    assert m.call_count == 1
    assert len(out) == len(fake)


def test_fetch_empty_cache_calls_yfinance_and_upserts(db_session):
    fake = _mk_yf_df(date(2024, 1, 1), 7)
    with patch("app.forex.data._yf_fetch", return_value=fake) as m:
        out = fetch_daily_bars(
            "EURUSD", date(2024, 1, 1), date(2024, 1, 7), db=db_session,
        )
    assert m.call_count == 1
    assert len(out) == len(fake)
    # Rows persisted
    persisted = db_session.query(ForexBar).filter(ForexBar.symbol == "EURUSD").all()
    assert len(persisted) == len(fake)


def test_fetch_full_cache_does_not_call_yfinance(db_session):
    # Pre-populate cache fully covering the requested range
    for d in pd.bdate_range("2024-01-01", "2024-01-05").date:
        db_session.add(ForexBar(
            symbol="EURUSD", bar_date=d,
            open=1.10, high=1.11, low=1.09, close=1.10,
        ))
    db_session.commit()

    with patch("app.forex.data._yf_fetch") as m:
        out = fetch_daily_bars(
            "EURUSD", date(2024, 1, 1), date(2024, 1, 5), db=db_session,
        )
    m.assert_not_called()
    assert len(out) == 5


def test_fetch_partial_cache_within_tolerance_serves_from_cache(db_session):
    # 5 cached bars over a 7-business-day range (2 missing) — tolerance allows ≤5 missing
    for d in pd.bdate_range("2024-01-01", "2024-01-05").date:
        db_session.add(ForexBar(
            symbol="EURUSD", bar_date=d,
            open=1.10, high=1.11, low=1.09, close=1.10,
        ))
    db_session.commit()

    with patch("app.forex.data._yf_fetch") as m:
        out = fetch_daily_bars(
            "EURUSD", date(2024, 1, 1), date(2024, 1, 12), db=db_session,
        )
    m.assert_not_called()
    assert len(out) == 5  # served from cache (incomplete but tolerable)


def test_fetch_significantly_stale_cache_triggers_refetch(db_session):
    # Only 1 cached bar over a 21-business-day range (>5 missing) → refetch
    db_session.add(ForexBar(
        symbol="EURUSD", bar_date=date(2024, 1, 1),
        open=1.10, high=1.11, low=1.09, close=1.10,
    ))
    db_session.commit()

    fake = _mk_yf_df(date(2024, 1, 1), 30)
    with patch("app.forex.data._yf_fetch", return_value=fake) as m:
        out = fetch_daily_bars(
            "EURUSD", date(2024, 1, 1), date(2024, 1, 31), db=db_session,
        )
    m.assert_called_once()
    assert len(out) == len(fake)


def test_fetch_yfinance_empty_response_does_not_crash(db_session):
    empty = pd.DataFrame(columns=["date", "open", "high", "low", "close"])
    with patch("app.forex.data._yf_fetch", return_value=empty):
        out = fetch_daily_bars(
            "EURUSD", date(2024, 1, 1), date(2024, 1, 7), db=db_session,
        )
    assert out.empty
    # Nothing persisted
    assert db_session.query(ForexBar).count() == 0


def test_fetch_upsert_skips_existing_dates(db_session):
    # Cache has 2 rows. Yfinance returns 5. Only 3 new rows should be inserted.
    for d in [date(2024, 1, 1), date(2024, 1, 2)]:
        db_session.add(ForexBar(
            symbol="EURUSD", bar_date=d,
            open=1.10, high=1.11, low=1.09, close=1.10,
        ))
    db_session.commit()

    fake = _mk_yf_df(date(2024, 1, 1), 7)  # 5 weekday bars
    # Force a refetch by querying outside the cache range too
    with patch("app.forex.data._yf_fetch", return_value=fake):
        fetch_daily_bars(
            "EURUSD", date(2024, 1, 1), date(2024, 1, 31), db=db_session,
        )

    persisted = db_session.query(ForexBar).filter(ForexBar.symbol == "EURUSD").all()
    # 2 pre-existing + 3 new (5 total minus 2 already cached) = 5 unique
    assert len(persisted) == 5
    # No duplicates by date
    assert len({b.bar_date for b in persisted}) == 5
