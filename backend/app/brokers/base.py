"""Abstract broker interface for multi-broker support."""

from abc import ABC, abstractmethod

from app.pipeline_types import AccountBalance, Position


class BrokerInterface(ABC):
    """Base class for all broker integrations."""

    @abstractmethod
    async def get_positions(self, account_id: str) -> list[Position]:
        """Fetch current portfolio positions."""

    @abstractmethod
    async def get_account_balance(self, account_id: str) -> AccountBalance:
        """Fetch account balances. Returns {cash_available, total_value}."""

    @abstractmethod
    async def place_order(
        self, account_id: str, ticker: str, action: str, quantity: int
    ) -> dict:
        """Place a buy or sell order. Returns execution result."""
