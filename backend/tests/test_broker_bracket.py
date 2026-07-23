"""AlpacaBroker stop-loss order construction.

Our locked design is a trailing stop with NO profit target, so the right Alpaca
order class is OTO (entry triggers one stop leg) — NOT bracket, which requires both
a stop and a take-profit leg.

These tests assert the REQUEST we build. They do not prove Alpaca accepts it — that
needs a live paper submission, verified separately before this reaches the executor.
"""

import pytest
from unittest.mock import MagicMock, patch

from alpaca.trading.enums import OrderClass, TimeInForce

from app.brokers.alpaca import AlpacaBroker


def _capture_submit():
    """A fake Alpaca client that records the order_data it was handed."""
    captured = {}
    order = MagicMock()
    order.id = "ord-1"
    order.status = "accepted"
    order.filled_qty = "0"

    client = MagicMock()

    def submit_order(order_data):
        captured["data"] = order_data
        return order

    client.submit_order.side_effect = submit_order
    return client, captured


@pytest.mark.asyncio
async def test_buy_with_stop_builds_oto_order():
    client, captured = _capture_submit()
    with patch("app.brokers.alpaca._get_client", return_value=client):
        await AlpacaBroker().place_order("default", "AAPL", "buy", 10, stop_price=94.0)

    data = captured["data"]
    assert data.order_class == OrderClass.OTO
    assert data.stop_loss.stop_price == 94.0
    assert data.take_profit is None          # no profit target, by design
    assert data.time_in_force == TimeInForce.DAY


@pytest.mark.asyncio
async def test_buy_without_stop_stays_a_simple_order():
    # Regression: existing callers pass no stop and must be unaffected.
    client, captured = _capture_submit()
    with patch("app.brokers.alpaca._get_client", return_value=client):
        await AlpacaBroker().place_order("default", "AAPL", "buy", 10)

    data = captured["data"]
    assert getattr(data, "order_class", None) in (None, OrderClass.SIMPLE)
    assert getattr(data, "stop_loss", None) is None


@pytest.mark.asyncio
async def test_sell_ignores_stop_price():
    # A stop leg only makes sense on the entry (buy). A sell must never carry one.
    client, captured = _capture_submit()
    with patch("app.brokers.alpaca._get_client", return_value=client):
        await AlpacaBroker().place_order("default", "AAPL", "sell", 10, stop_price=94.0)

    data = captured["data"]
    assert getattr(data, "stop_loss", None) is None


@pytest.mark.asyncio
async def test_crypto_buy_ignores_stop_price():
    # Alpaca crypto is simple-order only — an OTO stop leg would be REJECTED by the
    # API. PRD-002 failure mode: crypto can't carry a broker stop. Guards against a
    # future removal of the `not crypto` condition silently breaking crypto orders.
    client, captured = _capture_submit()
    with patch("app.brokers.alpaca._get_client", return_value=client):
        await AlpacaBroker().place_order("default", "BTC/USD", "buy", 1, stop_price=90000.0)

    data = captured["data"]
    assert getattr(data, "order_class", None) in (None, OrderClass.SIMPLE)
    assert getattr(data, "stop_loss", None) is None
    assert data.time_in_force == TimeInForce.GTC  # crypto path stays GTC, not DAY
