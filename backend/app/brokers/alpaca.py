"""Alpaca Markets broker — zero-commission stocks, ETFs, options, crypto."""

import asyncio
import logging

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
from alpaca.common.exceptions import APIError
from alpaca.trading.requests import MarketOrderRequest, StopLossRequest, StopOrderRequest

from app.brokers.base import BrokerInterface
from app.config import settings

logger = logging.getLogger(__name__)

# Alpaca SDK handles connection pooling internally
_client: TradingClient | None = None

# 069-fix: Shared broker-level lock so plan executor and legacy cycle
# executor can't interleave orders against the same Alpaca account.
# Any code calling place_order should rely on this lock; don't wrap calls
# in additional asyncio.Lock().
order_lock = asyncio.Lock()


def _get_client() -> TradingClient:
    global _client
    if _client is None:
        _client = TradingClient(
            api_key=settings.ALPACA_API_KEY,
            secret_key=settings.ALPACA_SECRET_KEY,
            paper=settings.ALPACA_PAPER,
        )
    return _client


class AlpacaBroker(BrokerInterface):
    """Alpaca API broker — stocks, ETFs, options, crypto. All zero commission."""

    async def get_positions(self, account_id: str) -> list[dict]:
        """Fetch all open positions from Alpaca."""
        client = _get_client()
        positions = await asyncio.to_thread(client.get_all_positions)
        return [
            {
                "instrument": {
                    "symbol": pos.symbol,
                    "assetType": pos.asset_class.value if pos.asset_class else "EQUITY",
                },
                "longQuantity": float(pos.qty),
                "marketValue": float(pos.market_value),
                "averagePrice": float(pos.avg_entry_price),
                "currentDayProfitLoss": float(pos.unrealized_intraday_pl),
                "currentDayProfitLossPercentage": float(pos.unrealized_intraday_plpc) * 100,
            }
            for pos in positions
        ]

    async def get_account_balance(self, account_id: str) -> dict:
        """Fetch account balances from Alpaca."""
        client = _get_client()
        account = await asyncio.to_thread(client.get_account)
        return {
            "cash_available": float(account.cash),
            "total_value": float(account.equity),
        }

    async def place_order(
        self, account_id: str, ticker: str, action: str, quantity: float,
        stop_price: float | None = None,
    ) -> dict:
        """Place a market buy or sell order on Alpaca.

        Sends ``quantity`` as a float; Alpaca fills it fractionally for
        fractionable equities and ETFs (which is every name in the trading
        universe) and for crypto pairs (which are natively fractional).
        There is NO whole-share fallback here: a fractional qty on a
        non-fractionable symbol (a few illiquid equities) is rejected by
        Alpaca, so callers must size whole-share qty for those.

        Time in force: equities use DAY (required for fractional orders);
        crypto pairs use GTC — Alpaca rejects DAY on crypto. A buy with a stop
        uses GTC so the inherited stop leg survives past the first close.

        ``stop_price`` attaches a broker-held stop to a BUY entry via an OTO
        order (entry triggers ONE stop leg — no take-profit, matching the
        trailing-stop design). Ignored on sells and on crypto (Alpaca crypto is
        simple-order only). OTO requires whole shares — the risk engine sizes
        whole shares, so callers passing a stop must pass an integer qty.

        Verified 2026-10-19 on the paper API: the OTO is accepted and its stop
        leg sits HELD (GTC) until the entry fills. Selling a position whose stop
        leg is still open needs that leg cancelled first — Alpaca reserves the
        shares for it.
        """
        if action not in ("buy", "sell"):
            raise ValueError(f"Invalid action: {action}. Must be 'buy' or 'sell'.")

        client = _get_client()

        from app.symbols import is_crypto
        crypto = is_crypto(ticker)
        attach_stop = stop_price is not None and action == "buy" and not crypto

        # The stop leg inherits the parent's TIF, and a DAY stop is cancelled at the
        # first close. OTO entries are whole shares, so GTC is allowed for them.
        fields = dict(
            symbol=ticker,
            qty=quantity,
            side=OrderSide.BUY if action == "buy" else OrderSide.SELL,
            time_in_force=TimeInForce.GTC if (crypto or attach_stop) else TimeInForce.DAY,
        )
        if attach_stop:
            fields["order_class"] = OrderClass.OTO
            fields["stop_loss"] = StopLossRequest(stop_price=stop_price)
        order_data = MarketOrderRequest(**fields)

        # 069-fix: Shared lock prevents concurrent orders across plan + legacy executors
        async with order_lock:
            order = await asyncio.to_thread(client.submit_order, order_data=order_data)
        logger.info(
            "Alpaca order submitted: %s %s %s — ID: %s, Status: %s",
            action, quantity, ticker, order.id, order.status,
        )

        legs = getattr(order, "legs", None) or []
        return {
            "status": str(order.status),
            "order_id": str(order.id),
            "filled_qty": float(order.filled_qty) if order.filled_qty else 0,
            # OTO entries carry exactly one stop leg; its id is how we later find,
            # cancel, or reconcile THIS portfolio's stop in a shared account.
            "stop_order_id": str(legs[0].id) if attach_stop and legs else None,
        }

    async def get_order(self, order_id: str) -> dict:
        """Current status + fill of one order. Status is the lower-case Alpaca value."""
        client = _get_client()
        order = await asyncio.to_thread(client.get_order_by_id, order_id)
        return {
            "status": _status(order.status),
            "filled_qty": float(order.filled_qty) if order.filled_qty else 0.0,
            "filled_avg_price": (
                float(order.filled_avg_price) if order.filled_avg_price else None
            ),
        }

    async def cancel_order(self, order_id: str) -> str:
        """Cancel an order and return its settled status.

        Cancels are asynchronous at Alpaca (pending_cancel → canceled), and a sell
        sent while the stop is still pending_cancel is rejected for reserved shares,
        so poll until it settles. If the order already filled (the stop fired a moment
        ago) Alpaca refuses the cancel — return "filled" so the caller records the
        fill instead of selling shares that are gone.
        """
        client = _get_client()
        try:
            await asyncio.to_thread(client.cancel_order_by_id, order_id)
        except APIError as e:
            logger.warning("Cancel of %s refused: %s", order_id, e)
        status = "unknown"
        for _ in range(5):
            status = (await self.get_order(order_id))["status"]
            if status != "pending_cancel":
                break
            await asyncio.sleep(0.5)
        return status

    async def place_stop_order(self, ticker: str, quantity: int, stop_price: float) -> dict:
        """Standalone GTC sell-stop — re-protects shares left after a partial sell."""
        client = _get_client()
        order_data = StopOrderRequest(
            symbol=ticker,
            qty=quantity,
            side=OrderSide.SELL,
            time_in_force=TimeInForce.GTC,
            stop_price=stop_price,
        )
        async with order_lock:
            order = await asyncio.to_thread(client.submit_order, order_data=order_data)
        logger.info("Alpaca stop placed: %s %s @ %s — ID: %s", ticker, quantity, stop_price, order.id)
        return {"order_id": str(order.id), "status": str(order.status)}


def _status(status) -> str:
    """OrderStatus enum (or raw string) → 'filled' / 'held' / 'canceled' ..."""
    return str(getattr(status, "value", status)).lower()
