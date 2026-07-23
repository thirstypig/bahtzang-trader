"""Unit tests for the risk engine — sizing and stop calculation.

The load-bearing math: risk is defined BEFORE entry. Position size falls out of the
stop, not the other way around.
"""

import pytest

from app.risk import compute_stop_price, compute_position_size, RiskError


class TestStopPrice:
    def test_stop_is_atr_multiple_below_entry(self):
        # entry 100, ATR 3, multiple 2 -> stop 6 below -> 94
        assert compute_stop_price(entry_price=100.0, atr=3.0, atr_multiple=2.0) == 94.0

    def test_default_multiple_is_two(self):
        assert compute_stop_price(entry_price=100.0, atr=3.0) == 94.0

    def test_missing_atr_raises(self):
        # No ATR -> no computable stop. Never guess one.
        with pytest.raises(RiskError):
            compute_stop_price(entry_price=100.0, atr=None)

    def test_zero_atr_raises(self):
        with pytest.raises(RiskError):
            compute_stop_price(entry_price=100.0, atr=0.0)


class TestPositionSize:
    def test_size_is_risk_budget_over_stop_distance(self):
        # equity 10000, risk 1% = $100 budget; entry 100, stop 94 -> $6 risk/share
        # 100 / 6 = 16.67 -> floor to 16 whole shares
        qty = compute_position_size(equity=10_000, risk_pct=0.01,
                                    entry_price=100.0, stop_price=94.0)
        assert qty == 16

    def test_volatile_name_gets_smaller_position(self):
        # Same $100 budget. Wider stop (bigger distance) -> fewer shares.
        tight = compute_position_size(equity=10_000, risk_pct=0.01,
                                      entry_price=100.0, stop_price=98.0)  # $2/share -> 50
        wide = compute_position_size(equity=10_000, risk_pct=0.01,
                                     entry_price=100.0, stop_price=90.0)   # $10/share -> 10
        assert tight == 50
        assert wide == 10
        assert wide < tight

    def test_rounds_down_to_whole_shares(self):
        # Bracket orders require whole shares.
        qty = compute_position_size(equity=10_000, risk_pct=0.01,
                                    entry_price=100.0, stop_price=93.0)  # $7 -> 14.28 -> 14
        assert qty == 14

    def test_budget_too_small_for_one_share_returns_zero(self):
        # $10 budget, $60 risk/share -> can't afford even one -> 0 (caller skips trade)
        qty = compute_position_size(equity=1_000, risk_pct=0.01,
                                    entry_price=500.0, stop_price=440.0)
        assert qty == 0

    def test_stop_not_below_entry_raises(self):
        # A stop at/above entry is nonsensical for a long.
        with pytest.raises(RiskError):
            compute_position_size(equity=10_000, risk_pct=0.01,
                                  entry_price=100.0, stop_price=100.0)
