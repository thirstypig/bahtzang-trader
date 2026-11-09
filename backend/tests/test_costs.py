"""Shared cost model (app/costs.py) — charter §1/§4: spread, fees, API, est. tax."""

from datetime import datetime
from types import SimpleNamespace

import pytest

from app.costs import (
    api_cost, estimated_tax, half_spread_cost, realized_sells, sell_fees,
)


def test_sell_fees():
    # $5,000 sold: SEC 20.60/1M → 0.103; FINRA TAF 100 × 0.000195 → 0.0195
    assert sell_fees(100, 50.0) == pytest.approx(0.1225)


def test_taf_capped():
    # 100,000 shares → TAF would be 19.50, capped at 9.79; SEC on $100k → 2.06
    assert sell_fees(100_000, 1.0) == pytest.approx(9.79 + 2.06)


def test_half_spread_cost():
    assert half_spread_cost(10, 49.98, 50.02) == pytest.approx(0.20)


def test_bad_quote_is_none():
    assert half_spread_cost(10, 0, 50.0) is None
    assert half_spread_cost(10, 50.02, 49.98) is None
    assert half_spread_cost(10, None, 50.0) is None


def test_api_cost():
    u = SimpleNamespace(input_tokens=1000, output_tokens=500,
                        cache_read_input_tokens=2000, cache_creation_input_tokens=0)
    assert api_cost(u) == pytest.approx(0.003 + 0.0075 + 0.0006)


def test_api_cost_none_fields():
    u = SimpleNamespace(input_tokens=1000, output_tokens=None,
                        cache_read_input_tokens=None, cache_creation_input_tokens=None)
    assert api_cost(u) == pytest.approx(0.003)


def _t(i, action, qty, price):
    return SimpleNamespace(id=i, ticker="AAPL", action=action, quantity=qty, price=price,
                           timestamp=datetime(2026, 11, 2, 15, i))


def test_realized_sells_avg_cost():
    sells = realized_sells([_t(1, "buy", 10, 10), _t(2, "buy", 10, 20), _t(3, "sell", 5, 30)])
    assert len(sells) == 1
    s = sells[0]
    assert (s.trade_id, s.qty, s.proceeds, s.cost_basis, s.gain) == (3, 5, 150, 75, 75)


def test_tax_on_net_gain_floored():
    assert estimated_tax([100, -40]) == pytest.approx(14.4)
    assert estimated_tax([-50]) == 0
    assert estimated_tax([]) == 0
