"""Daily candle reversal patterns: pin bars and engulfing.

Pin bar (default): dominant wick ≥ 2× body, opposing wick ≤ 0.5× body.
Engulfing (body-only): current body fully covers prior body, with opposite
direction. Wicks ignored to reduce noise from intraday spikes.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Candle:
    open: float
    high: float
    low: float
    close: float

    @property
    def body(self) -> float:
        return abs(self.close - self.open)

    @property
    def upper_wick(self) -> float:
        return self.high - max(self.open, self.close)

    @property
    def lower_wick(self) -> float:
        return min(self.open, self.close) - self.low

    @property
    def is_bullish(self) -> bool:
        return self.close > self.open

    @property
    def is_bearish(self) -> bool:
        return self.close < self.open


def is_bullish_pin_bar(c: Candle, wick_ratio: float = 2.0, opposing_max: float = 0.5) -> bool:
    if c.body <= 0:
        return False
    return c.lower_wick >= wick_ratio * c.body and c.upper_wick <= opposing_max * c.body


def is_bearish_pin_bar(c: Candle, wick_ratio: float = 2.0, opposing_max: float = 0.5) -> bool:
    if c.body <= 0:
        return False
    return c.upper_wick >= wick_ratio * c.body and c.lower_wick <= opposing_max * c.body


def is_bullish_engulfing(prev: Candle, curr: Candle) -> bool:
    if not (prev.is_bearish and curr.is_bullish):
        return False
    prev_body_low = min(prev.open, prev.close)
    prev_body_high = max(prev.open, prev.close)
    curr_body_low = min(curr.open, curr.close)
    curr_body_high = max(curr.open, curr.close)
    return curr_body_low <= prev_body_low and curr_body_high >= prev_body_high


def is_bearish_engulfing(prev: Candle, curr: Candle) -> bool:
    if not (prev.is_bullish and curr.is_bearish):
        return False
    prev_body_low = min(prev.open, prev.close)
    prev_body_high = max(prev.open, prev.close)
    curr_body_low = min(curr.open, curr.close)
    curr_body_high = max(curr.open, curr.close)
    return curr_body_low <= prev_body_low and curr_body_high >= prev_body_high


def detect_bullish_reversal(prev: Candle | None, curr: Candle) -> str | None:
    """Return the name of the bullish reversal pattern present, or None."""
    if is_bullish_pin_bar(curr):
        return "bullish_pin_bar"
    if prev is not None and is_bullish_engulfing(prev, curr):
        return "bullish_engulfing"
    return None


def detect_bearish_reversal(prev: Candle | None, curr: Candle) -> str | None:
    if is_bearish_pin_bar(curr):
        return "bearish_pin_bar"
    if prev is not None and is_bearish_engulfing(prev, curr):
        return "bearish_engulfing"
    return None
