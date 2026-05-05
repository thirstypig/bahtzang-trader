"""Pivot detection, clustering, and zone construction."""

from datetime import date

import pandas as pd

from app.forex.zones import (
    build_zones,
    cluster_indices_by_price,
    find_pivot_highs,
    find_pivot_lows,
)


def _bars(rows):
    return pd.DataFrame(rows, columns=["date", "open", "high", "low", "close"])


def test_find_pivot_highs_5bar_window():
    df = _bars([
        (date(2024, 1, 1), 1.10, 1.11, 1.09, 1.10),
        (date(2024, 1, 2), 1.10, 1.12, 1.10, 1.11),
        (date(2024, 1, 3), 1.11, 1.20, 1.10, 1.15),  # pivot high (max in 5-bar window)
        (date(2024, 1, 4), 1.15, 1.16, 1.13, 1.14),
        (date(2024, 1, 5), 1.14, 1.15, 1.12, 1.13),
    ])
    assert find_pivot_highs(df, n=2) == [2]


def test_find_pivot_highs_strict_inequality():
    df = _bars([
        (date(2024, 1, i + 1), 1.0, 1.20, 0.95, 1.0)
        for i in range(5)
    ])
    assert find_pivot_highs(df, n=2) == []


def test_find_pivot_lows_5bar_window():
    df = _bars([
        (date(2024, 1, 1), 1.10, 1.11, 1.09, 1.10),
        (date(2024, 1, 2), 1.10, 1.10, 1.05, 1.06),
        (date(2024, 1, 3), 1.06, 1.07, 1.00, 1.05),  # pivot low
        (date(2024, 1, 4), 1.05, 1.08, 1.03, 1.07),
        (date(2024, 1, 5), 1.07, 1.10, 1.04, 1.09),
    ])
    assert find_pivot_lows(df, n=2) == [2]


def test_cluster_chain_within_pct():
    # Three pivots at 1.00, 1.004, 1.008 — each within 0.5% of the next
    indices = [0, 1, 2]
    prices = [1.000, 1.004, 1.008]
    clusters = cluster_indices_by_price(prices, indices, pct=0.005)
    assert len(clusters) == 1
    assert sorted(clusters[0]) == [0, 1, 2]


def test_cluster_breaks_outside_pct():
    # 1.000 and 1.004 are within 0.5% (cluster), 1.500 is far away (separate)
    indices = [0, 1, 2]
    prices = [1.000, 1.004, 1.500]
    clusters = cluster_indices_by_price(prices, indices, pct=0.005)
    assert len(clusters) == 2


def test_build_zones_creates_resistance_zone():
    # Repeat pivot highs near 1.20 → resistance zone
    rows = []
    for i in range(20):
        if i in (5, 10, 15):
            rows.append((date(2024, 1, i + 1), 1.10, 1.20, 1.09, 1.15))
        else:
            rows.append((date(2024, 1, i + 1), 1.10, 1.12, 1.08, 1.11))
    df = _bars(rows)
    zones = build_zones(df, lookback_weeks=100, cluster_pct=0.005, pivot_n=2)
    resistance = [z for z in zones if z.kind == "resistance"]
    assert len(resistance) >= 1
    z = resistance[0]
    assert z.top == 1.20
    assert z.bottom == 1.15
    assert 1.15 < z.midpoint < 1.20


def test_zone_midpoint():
    from app.forex.zones import Zone
    z = Zone(kind="resistance", top=1.20, bottom=1.10)
    assert z.midpoint == 1.15
