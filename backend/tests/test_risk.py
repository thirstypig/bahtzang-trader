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


from app.risk import round_stop_price, size_entry  # noqa: E402


def _size(**kw):
    args = dict(portfolio_value=10_000, cash=10_000, entry_price=50, atr=2.0)
    args.update(kw)
    return size_entry(**args)


class TestRoundStopPrice:
    def test_round_stop_price(self):
        assert round_stop_price(46.239) == 46.23
        assert round_stop_price(0.123456) == 0.1234
        assert round_stop_price(11.57) == 11.57


class TestSizeEntry:
    def test_risk_sized(self):
        assert _size() == (25, 46.0)

    def test_tight_stop_capped_by_cash(self):
        qty, _ = _size(cash=1_000, entry_price=100, atr=0.25)
        assert qty == 9

    def test_tight_stop_capped_by_position_cap(self):
        qty, _ = _size(entry_price=100, atr=0.25)
        assert qty == 20

    def test_earnings_tomorrow_halves(self):
        assert _size(earnings_days=1)[0] == 12
        assert _size(earnings_days=2)[0] == 17
        assert _size(earnings_days=5)[0] == 25

    def test_no_atr_raises(self):
        with pytest.raises(RiskError):
            _size(atr=None)

    def test_stop_at_or_below_zero_raises(self):
        with pytest.raises(RiskError):
            _size(entry_price=1.0, atr=0.6)

    def test_too_small_returns_zero(self):
        qty, _ = _size(portfolio_value=100, cash=100, entry_price=500, atr=10)
        assert qty == 0

    def test_stop_is_rounded(self):
        _, stop = _size(atr=1.3333)
        assert stop == 47.33


class TestPositionCapCountsHolding:
    def test_position_cap_counts_existing_holding(self):
        # Already hold $1,800 of a $10k portfolio → only $200 more fits under 20%.
        qty, _ = _size(entry_price=50, atr=0.25, held_value=1_800)
        assert qty == 4

    def test_already_at_cap_returns_zero(self):
        qty, _ = _size(held_value=2_500)
        assert qty == 0


class TestPerStrategyLimits:
    """Charter 2026-11-09: conservative = 0.5% risk, 10% max position;
    aggressive = 1% risk, 20% max position."""

    def test_profile_limits(self):
        from app.risk import limits_for_profile
        assert limits_for_profile("conservative") == (0.005, 0.10)
        assert limits_for_profile("aggressive") == (0.01, 0.20)
        assert limits_for_profile("moderate") == (0.01, 0.20)   # default = charter caps

    def test_conservative_risks_half(self):
        qty, _ = _size(risk_pct=0.005, max_position_pct=0.10)
        assert qty == 12            # $50 risk / $4 stop distance

    def test_conservative_position_cap_is_ten_pct(self):
        qty, _ = _size(entry_price=100, atr=0.25, risk_pct=0.005, max_position_pct=0.10)
        assert qty == 10            # 10% of $10k / $100
