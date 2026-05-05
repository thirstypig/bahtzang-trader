"""Weekly support/resistance zone construction from pivot clusters.

Pivot definition: a high is a pivot if the n bars before and after all have
strictly lower highs (mirror for lows). Default n=2 per the strategy spec.

Clustering: single-linkage on sorted prices — pivots within `cluster_pct` of
their nearest neighbor by price form a chain, all chained members share a zone.

Zone edges (symmetric construction):
  - Resistance (from pivot highs): top=max(high), bottom=min(close)
  - Support    (from pivot lows):  bottom=min(low),  top=max(close)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import pandas as pd


@dataclass
class Zone:
    kind: str  # "support" | "resistance"
    top: float
    bottom: float
    pivot_dates: list[date] = field(default_factory=list)

    @property
    def midpoint(self) -> float:
        return (self.top + self.bottom) / 2.0

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "top": self.top,
            "bottom": self.bottom,
            "midpoint": self.midpoint,
            "pivot_dates": [str(d) for d in self.pivot_dates],
        }


def find_pivot_highs(df: pd.DataFrame, n: int = 2) -> list[int]:
    out: list[int] = []
    highs = df["high"].to_numpy()
    for i in range(n, len(highs) - n):
        center = highs[i]
        if all(highs[i - k] < center for k in range(1, n + 1)) and \
           all(highs[i + k] < center for k in range(1, n + 1)):
            out.append(i)
    return out


def find_pivot_lows(df: pd.DataFrame, n: int = 2) -> list[int]:
    out: list[int] = []
    lows = df["low"].to_numpy()
    for i in range(n, len(lows) - n):
        center = lows[i]
        if all(lows[i - k] > center for k in range(1, n + 1)) and \
           all(lows[i + k] > center for k in range(1, n + 1)):
            out.append(i)
    return out


def cluster_indices_by_price(
    prices: list[float], indices: list[int], pct: float
) -> list[list[int]]:
    if not indices:
        return []
    paired = sorted(zip(prices, indices), key=lambda x: x[0])
    clusters: list[list[int]] = []
    current = [paired[0][1]]
    last_price = paired[0][0]
    for price, idx in paired[1:]:
        if last_price > 0 and abs(price - last_price) / last_price <= pct:
            current.append(idx)
        else:
            clusters.append(current)
            current = [idx]
        last_price = price
    clusters.append(current)
    return clusters


def build_zones(
    weekly_df: pd.DataFrame,
    lookback_weeks: int = 100,
    cluster_pct: float = 0.005,
    pivot_n: int = 2,
) -> list[Zone]:
    if weekly_df.empty:
        return []
    df = weekly_df.tail(lookback_weeks).reset_index(drop=True)
    has_date = "date" in df.columns

    zones: list[Zone] = []

    high_idx = find_pivot_highs(df, n=pivot_n)
    if high_idx:
        clusters = cluster_indices_by_price(
            [float(df["high"].iloc[i]) for i in high_idx], high_idx, cluster_pct
        )
        for cluster in clusters:
            top = max(float(df["high"].iloc[i]) for i in cluster)
            bottom = min(float(df["close"].iloc[i]) for i in cluster)
            if bottom >= top:
                continue
            dates = [df["date"].iloc[i] for i in cluster] if has_date else []
            zones.append(Zone(kind="resistance", top=top, bottom=bottom, pivot_dates=dates))

    low_idx = find_pivot_lows(df, n=pivot_n)
    if low_idx:
        clusters = cluster_indices_by_price(
            [float(df["low"].iloc[i]) for i in low_idx], low_idx, cluster_pct
        )
        for cluster in clusters:
            bottom = min(float(df["low"].iloc[i]) for i in cluster)
            top = max(float(df["close"].iloc[i]) for i in cluster)
            if bottom >= top:
                continue
            dates = [df["date"].iloc[i] for i in cluster] if has_date else []
            zones.append(Zone(kind="support", top=top, bottom=bottom, pivot_dates=dates))

    return zones
