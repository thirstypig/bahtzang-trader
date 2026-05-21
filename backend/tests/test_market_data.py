"""get_quotes must survive a partially-failing batch.

Regression: with a ~100-name candidate universe, a single ticker raising inside
the asyncio.gather (network blip, malformed JSON, rate-limit error) would —
before the return_exceptions hardening — propagate and abort the ENTIRE
market-data fetch for the cycle, taking every portfolio down with it. The
contract the executor depends on: get_quotes returns the quotes it could fetch
and silently drops the ones it couldn't (their prices are backfilled from
Alpaca bars in the indicator-patch step).
"""

import pytest
from unittest.mock import patch

from app import market_data


async def _quote(ticker: str) -> dict:
    return {"ticker": ticker, "price": 10.0, "change_pct": 0.0, "volume": 0}


@pytest.mark.unit
class TestGetQuotesPartialFailure:
    async def test_drops_failed_tickers_keeps_successes(self):
        """One raising ticker is dropped; the rest of the batch still returns."""

        async def fake(ticker):
            if ticker == "BAD":
                raise RuntimeError("network blip")
            return await _quote(ticker)

        with patch("app.market_data.get_quote", side_effect=fake):
            result = await market_data.get_quotes(["AAPL", "BAD", "MSFT"])

        assert {q["ticker"] for q in result} == {"AAPL", "MSFT"}

    async def test_all_failures_returns_empty_not_raise(self):
        """A fully-failed batch yields [] — the caller never sees an exception."""
        with patch("app.market_data.get_quote", side_effect=RuntimeError("down")):
            result = await market_data.get_quotes(["AAPL", "MSFT"])

        assert result == []

    async def test_all_success_passthrough(self):
        """The happy path is unchanged — every quote comes back."""
        with patch("app.market_data.get_quote", side_effect=_quote):
            result = await market_data.get_quotes(["AAPL", "MSFT"])

        assert {q["ticker"] for q in result} == {"AAPL", "MSFT"}
