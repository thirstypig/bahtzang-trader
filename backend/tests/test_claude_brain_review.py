"""Tests for claude_brain.review_trade_decision() — single-decision oversight function.

Verifies:
  - Normal signal → confirmed=True
  - Earnings proximity context → Claude can return override (confirmed=False)
  - Malformed JSON response → fail-closed (confirmed=True)
  - APITimeoutError → fail-closed (confirmed=True)
  - Kill switch context → Claude can return override
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

import anthropic

from app import claude_brain


def _mock_message(text: str) -> MagicMock:
    """Minimal Anthropic message mock with a single text content block."""
    msg = MagicMock()
    msg.content = [MagicMock(text=text)]
    return msg


def _make_portfolio(
    strategy_id: str = "sma_crossover",
    trading_goal: str = "maximize_returns",
    risk_profile: str = "moderate",
) -> MagicMock:
    """Return a minimal Portfolio-duck object for testing."""
    p = MagicMock()
    p.strategy_id = strategy_id
    p.trading_goal = trading_goal
    p.risk_profile = risk_profile
    return p


_NORMAL_BUY = {
    "action": "buy",
    "ticker": "AAPL",
    "quantity": 5.0,
    "confidence": 0.75,
    "reasoning": "SMA golden cross",
}

_CONTEXT = {
    "cash_available": 50_000.0,
    "positions": [],
    "quotes": [{"ticker": "AAPL", "price": 150.0, "change_pct": 0.5, "volume": 1_000_000}],
    "news": [],
    "technicals_csv": "",
    "earnings_csv": "",
    "sector_csv": "",
    "trading_goal": "maximize_returns",
    "risk_profile": "moderate",
}


@pytest.mark.integration
class TestClaudeBrainReview:

    async def test_review_returns_confirmed_for_normal_signal(self):
        """Normal buy signal with no red flags → Claude confirms, confirmed=True."""
        response = '{"confirmed": true, "override_decision": null, "reasoning": "Signal is valid", "override_confidence": 0.0}'

        with patch_create(response) as mock_create:
            result = await claude_brain.review_trade_decision(
                _NORMAL_BUY, _CONTEXT, _make_portfolio()
            )

        assert result["confirmed"] is True
        assert result["override_decision"] is None
        assert "Signal is valid" in result["reasoning"]
        assert result["override_confidence"] == pytest.approx(0.0)
        mock_create.assert_called_once()

    async def test_review_returns_override_for_earnings_proximity(self):
        """Earnings within 2 days → Claude can return confirmed=False with override to hold."""
        response = (
            '{"confirmed": false, '
            '"override_decision": {"action": "hold", "ticker": "AAPL", "quantity": 0, '
            '"reasoning": "Earnings in 1 day — binary event risk", "confidence": 0.85}, '
            '"reasoning": "Earnings announcement imminent", "override_confidence": 0.85}'
        )
        context_with_earnings = {
            **_CONTEXT,
            "earnings_csv": "EARNINGS CALENDAR\nticker,days_until,date\nAAPL,1,2026-05-13",
        }

        with patch_create(response):
            result = await claude_brain.review_trade_decision(
                _NORMAL_BUY, context_with_earnings, _make_portfolio()
            )

        assert result["confirmed"] is False
        assert result["override_decision"]["action"] == "hold"
        assert result["override_confidence"] == pytest.approx(0.85)

    async def test_review_handles_malformed_response_defaults_to_confirmed(self):
        """Plain-text or non-JSON response → fail-closed, confirmed=True."""
        with patch_create("I think the market looks risky and you should hold."):
            result = await claude_brain.review_trade_decision(
                _NORMAL_BUY, _CONTEXT, _make_portfolio()
            )

        assert result["confirmed"] is True
        assert result["override_decision"] is None
        assert "Malformed" in result["reasoning"]

    async def test_review_handles_timeout_defaults_to_confirmed(self):
        """APITimeoutError → fail-closed, confirmed=True, no exception raised."""
        with patch_create_raises(anthropic.APITimeoutError(request=MagicMock())):
            result = await claude_brain.review_trade_decision(
                _NORMAL_BUY, _CONTEXT, _make_portfolio()
            )

        assert result["confirmed"] is True
        assert result["override_decision"] is None
        assert "timed out" in result["reasoning"].lower()

    async def test_review_respects_kill_switch_in_context(self):
        """Kill switch in context → Claude sees the flag and can override to hold."""
        response = (
            '{"confirmed": false, '
            '"override_decision": {"action": "hold", "ticker": "AAPL", "quantity": 0, '
            '"reasoning": "Kill switch active", "confidence": 1.0}, '
            '"reasoning": "Kill switch is active — no new trades", "override_confidence": 1.0}'
        )
        context_with_kill = {**_CONTEXT, "kill_switch": True}

        with patch_create(response):
            result = await claude_brain.review_trade_decision(
                _NORMAL_BUY, context_with_kill, _make_portfolio()
            )

        assert result["confirmed"] is False
        assert result["override_decision"]["action"] == "hold"
        assert result["override_confidence"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

from contextlib import contextmanager
from unittest.mock import patch


@contextmanager
def patch_create(response_text: str):
    """Patch claude_brain.client.messages.create to return a fake message."""
    with patch.object(
        claude_brain.client.messages, "create", new_callable=AsyncMock
    ) as mock:
        mock.return_value = _mock_message(response_text)
        yield mock


@contextmanager
def patch_create_raises(exc: Exception):
    """Patch claude_brain.client.messages.create to raise an exception."""
    with patch.object(
        claude_brain.client.messages, "create", new_callable=AsyncMock
    ) as mock:
        mock.side_effect = exc
        yield mock
