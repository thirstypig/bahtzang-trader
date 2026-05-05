"""Reversal-pattern detectors: pin bar (2x wick) and body-engulfing."""

from app.forex.patterns import (
    Candle,
    detect_bearish_reversal,
    detect_bullish_reversal,
    is_bearish_engulfing,
    is_bearish_pin_bar,
    is_bullish_engulfing,
    is_bullish_pin_bar,
)


def test_bullish_pin_bar_passes_thresholds():
    # body=0.1, lower_wick=0.3 (3x), upper_wick=0 → pass
    c = Candle(open=1.10, high=1.20, low=0.90, close=1.20)
    # Recompute: body=0.1, upper_wick=0, lower_wick=0.20 → 2x ratio met, opposing 0
    assert is_bullish_pin_bar(c)


def test_bullish_pin_bar_rejects_short_wick():
    # body=0.05, lower_wick=0.05 (1x) → fail wick_ratio
    c = Candle(open=1.10, high=1.16, low=1.04, close=1.15)
    assert not is_bullish_pin_bar(c)


def test_pin_bar_rejects_doji():
    c = Candle(open=1.10, high=1.20, low=1.00, close=1.10)
    assert not is_bullish_pin_bar(c)
    assert not is_bearish_pin_bar(c)


def test_bearish_pin_bar():
    # body=0.05, upper_wick=0.20 (4x), lower_wick=0
    c = Candle(open=1.20, high=1.40, low=1.15, close=1.15)
    assert is_bearish_pin_bar(c)


def test_bullish_engulfing():
    prev = Candle(open=1.10, high=1.11, low=1.05, close=1.06)  # bearish
    curr = Candle(open=1.05, high=1.13, low=1.04, close=1.12)  # bullish, body engulfs prev body
    assert is_bullish_engulfing(prev, curr)


def test_bullish_engulfing_requires_opposite_color():
    prev = Candle(open=1.05, high=1.11, low=1.04, close=1.10)  # bullish — wrong direction
    curr = Candle(open=1.04, high=1.13, low=1.03, close=1.12)
    assert not is_bullish_engulfing(prev, curr)


def test_bullish_engulfing_requires_full_body_cover():
    prev = Candle(open=1.10, high=1.11, low=1.05, close=1.06)
    # curr body 1.07–1.09 is inside prev body 1.06–1.10
    curr = Candle(open=1.07, high=1.12, low=1.06, close=1.09)
    assert not is_bullish_engulfing(prev, curr)


def test_bearish_engulfing():
    prev = Candle(open=1.05, high=1.11, low=1.04, close=1.10)  # bullish
    curr = Candle(open=1.11, high=1.12, low=1.03, close=1.04)  # bearish, body engulfs
    assert is_bearish_engulfing(prev, curr)


def test_detect_bullish_reversal_returns_name():
    pin = Candle(open=1.10, high=1.20, low=0.90, close=1.20)
    assert detect_bullish_reversal(None, pin) == "bullish_pin_bar"
    prev = Candle(open=1.10, high=1.11, low=1.05, close=1.06)
    eng = Candle(open=1.05, high=1.13, low=1.04, close=1.12)
    assert detect_bullish_reversal(prev, eng) == "bullish_engulfing"


def test_detect_bearish_reversal_returns_none_on_clean_candle():
    plain = Candle(open=1.10, high=1.11, low=1.09, close=1.105)
    assert detect_bearish_reversal(None, plain) is None
