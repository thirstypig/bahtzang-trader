"""Typed dicts for the trading pipeline data structures.

009-fix: Replace bare dict types with TypedDict for type safety.
"""

from typing import TypedDict


class PositionInstrument(TypedDict):
    symbol: str
    asset_type: str


class Position(TypedDict):
    instrument: PositionInstrument
    quantity: float
    market_value: float
    cost_basis: float
    unrealized_pnl: float
    unrealized_pnl_pct: float


class AccountBalance(TypedDict):
    cash_available: float
    total_value: float


class Quote(TypedDict):
    ticker: str
    price: float
    change_pct: float
    volume: int


class NewsItem(TypedDict):
    title: str
    source: str
    url: str
    sentiment: str
    relevance: float


class TradeDecision(TypedDict):
    action: str          # "buy" | "sell" | "hold"
    ticker: str
    quantity: int
    reasoning: str
    confidence: float
    price: float | None


class CycleResult(TypedDict):
    trade_id: int
    action: str
    ticker: str
    quantity: int
    price: float | None
    executed: bool
    guardrail_passed: bool
    guardrail_block_reason: str | None
    reasoning: str
    confidence: float
