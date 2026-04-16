"""Alpaca Markets broker — zero-commission stocks, ETFs, options, crypto."""

import asyncio
import logging

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest

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
        self, account_id: str, ticker: str, action: str, quantity: float
    ) -> dict:
        """Place a market buy or sell order on Alpaca.

        Supports fractional shares — Alpaca accepts float qty for eligible
        securities. Falls back to whole-share qty for crypto/options.
        """
        if action not in ("buy", "sell"):
            raise ValueError(f"Invalid action: {action}. Must be 'buy' or 'sell'.")

        client = _get_client()

        # Fractional shares use DAY time_in_force; whole shares use DAY as well.
        # Alpaca SDK accepts float qty for eligible tickers.
        order_data = MarketOrderRequest(
            symbol=ticker,
            qty=quantity,
            side=OrderSide.BUY if action == "buy" else OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
        )

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
