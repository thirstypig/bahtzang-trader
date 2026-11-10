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
    # The stop leg inherits the parent's TIF. DAY would cancel the stop at the first
    # close (seen on a live paper order 2026-10-19), leaving the position unprotected.
    assert data.time_in_force == TimeInForce.GTC


@pytest.mark.asyncio
async def test_buy_without_stop_stays_a_simple_order():
    # Regression: existing callers pass no stop and must be unaffected.
    client, captured = _capture_submit()
    with patch("app.brokers.alpaca._get_client", return_value=client):
        await AlpacaBroker().place_order("default", "AAPL", "buy", 10)

    data = captured["data"]
    assert getattr(data, "order_class", None) in (None, OrderClass.SIMPLE)
    assert getattr(data, "stop_loss", None) is None
    assert data.time_in_force == TimeInForce.DAY  # fractional orders require DAY


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


# --- Stop lifecycle (risk-engine wiring) -----------------------------------

from alpaca.common.exceptions import APIError  # noqa: E402
from alpaca.trading.enums import OrderStatus, OrderSide  # noqa: E402


def _order(status, filled_qty="0", filled_avg_price=None, legs=None, oid="ord-1", filled_at=None):
    o = MagicMock()
    o.filled_at = filled_at
    o.id = oid
    o.status = status
    o.filled_qty = filled_qty
    o.filled_avg_price = filled_avg_price
    o.legs = legs
    return o


@pytest.mark.asyncio
async def test_oto_result_includes_stop_leg_id():
    client = MagicMock()
    client.submit_order.return_value = _order(
        OrderStatus.ACCEPTED, legs=[_order(OrderStatus.HELD, oid="leg-9")]
    )
    with patch("app.brokers.alpaca._get_client", return_value=client):
        res = await AlpacaBroker().place_order("default", "F", "buy", 1, stop_price=11.57)
    assert res["stop_order_id"] == "leg-9"


@pytest.mark.asyncio
async def test_plain_order_has_no_stop_leg_id():
    client = MagicMock()
    client.submit_order.return_value = _order(OrderStatus.ACCEPTED, legs=None)
    with patch("app.brokers.alpaca._get_client", return_value=client):
        res = await AlpacaBroker().place_order("default", "F", "sell", 1)
    assert res["stop_order_id"] is None


@pytest.mark.asyncio
async def test_get_order_normalizes_status():
    client = MagicMock()
    client.get_order_by_id.return_value = _order(OrderStatus.FILLED, "10", "46.0")
    with patch("app.brokers.alpaca._get_client", return_value=client):
        res = await AlpacaBroker().get_order("leg-1")
    assert res == {"status": "filled", "filled_qty": 10.0, "filled_avg_price": 46.0, "filled_at": None}


@pytest.mark.asyncio
async def test_get_order_returns_fill_time():
    from datetime import datetime, timezone
    at = datetime(2026, 11, 13, 19, 45, tzinfo=timezone.utc)
    client = MagicMock()
    client.get_order_by_id.return_value = _order(OrderStatus.FILLED, "10", "46.0", filled_at=at)
    with patch("app.brokers.alpaca._get_client", return_value=client):
        res = await AlpacaBroker().get_order("leg-1")
    assert res["filled_at"] == at


@pytest.mark.asyncio
async def test_cancel_order_waits_out_pending_cancel():
    client = MagicMock()
    client.get_order_by_id.side_effect = [
        _order(OrderStatus.PENDING_CANCEL), _order(OrderStatus.CANCELED),
    ]
    with patch("app.brokers.alpaca._get_client", return_value=client), \
         patch("app.brokers.alpaca.asyncio.sleep", new=_no_sleep):
        status = await AlpacaBroker().cancel_order("leg-1")
    client.cancel_order_by_id.assert_called_once_with("leg-1")
    assert status == "canceled"


@pytest.mark.asyncio
async def test_cancel_order_reports_filled_when_raced():
    client = MagicMock()
    client.cancel_order_by_id.side_effect = APIError('{"code":42210000,"message":"order is not cancelable"}')
    client.get_order_by_id.return_value = _order(OrderStatus.FILLED, "10", "46.0")
    with patch("app.brokers.alpaca._get_client", return_value=client), \
         patch("app.brokers.alpaca.asyncio.sleep", new=_no_sleep):
        status = await AlpacaBroker().cancel_order("leg-1")
    assert status == "filled"


@pytest.mark.asyncio
async def test_place_stop_order_is_gtc_sell_stop():
    client, captured = _capture_submit()
    with patch("app.brokers.alpaca._get_client", return_value=client):
        res = await AlpacaBroker().place_stop_order("AAPL", 7, 46.0)
    data = captured["data"]
    assert data.side == OrderSide.SELL
    assert data.qty == 7
    assert data.stop_price == 46.0
    assert data.time_in_force == TimeInForce.GTC
    assert res["order_id"] == "ord-1"


async def _no_sleep(_):
    return None
