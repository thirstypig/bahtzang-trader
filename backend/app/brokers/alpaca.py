"""Alpaca Markets broker — zero-commission stocks, ETFs, options, crypto."""

import asyncio
import logging

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest, StopLossRequest

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
        crypto pairs use GTC — Alpaca rejects DAY on crypto.

        ``stop_price`` attaches a broker-held stop to a BUY entry via an OTO
        order (entry triggers ONE stop leg — no take-profit, matching the
        trailing-stop design). Ignored on sells and on crypto (Alpaca crypto is
        simple-order only). OTO requires whole shares — the risk engine sizes
        whole shares, so callers passing a stop must pass an integer qty.

        NOTE: OTO-with-a-lone-stop is verified to CONSTRUCT; acceptance by the
        Alpaca paper API must be confirmed with a live paper order before this
        path is trusted in the executor.
        """
        if action not in ("buy", "sell"):
            raise ValueError(f"Invalid action: {action}. Must be 'buy' or 'sell'.")

        client = _get_client()

        from app.symbols import is_crypto
        crypto = is_crypto(ticker)
        attach_stop = stop_price is not None and action == "buy" and not crypto

        fields = dict(
            symbol=ticker,
            qty=quantity,
            side=OrderSide.BUY if action == "buy" else OrderSide.SELL,
            time_in_force=TimeInForce.GTC if crypto else TimeInForce.DAY,
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

        return {
            "status": str(order.status),
            "order_id": str(order.id),
            "filled_qty": float(order.filled_qty) if order.filled_qty else 0,
        }
