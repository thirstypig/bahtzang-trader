"""Guard against bare crypto symbols in GOAL_PROMPTS.

The root cause of the BTC silent-block bug (2026-05-14): BTC and ETH were in
GOAL_PROMPTS but the pipeline uses StockHistoricalDataClient (equities only).
Alpaca returned ~$35 for the equities instrument named 'BTC', so every BTC
buy was blocked by the $1 minimum guardrail. This test prevents re-introduction.
"""
import re
import pytest
from app.claude_brain import GOAL_PROMPTS

BARE_CRYPTO = {"BTC", "ETH", "SOL", "ADA", "DOGE", "XRP", "MATIC", "AVAX"}


def _word_boundaries(text: str, symbol: str) -> bool:
    """True if symbol appears as a standalone word (not part of BTC/USD pair format)."""
    return bool(re.search(rf"\b{re.escape(symbol)}\b(?!/)", text))


@pytest.mark.unit
class TestGoalPromptNoCrypto:
    def test_maximize_returns_has_no_bare_crypto(self):
        """maximize_returns prompt must not suggest bare crypto symbols."""
        prompt = GOAL_PROMPTS["maximize_returns"]
        for symbol in BARE_CRYPTO:
            assert not _word_boundaries(prompt, symbol), (
                f"Bare crypto symbol '{symbol}' found in maximize_returns prompt. "
                f"Use '{symbol}/USD' format (Alpaca crypto client required) or omit entirely."
            )

    def test_swing_trading_has_no_bare_crypto(self):
        """swing_trading prompt must not suggest bare crypto symbols."""
        prompt = GOAL_PROMPTS["swing_trading"]
        for symbol in BARE_CRYPTO:
            assert not _word_boundaries(prompt, symbol), (
                f"Bare crypto symbol '{symbol}' found in swing_trading prompt. "
                f"Use '{symbol}/USD' format (Alpaca crypto client required) or omit entirely."
            )

    def test_all_goals_have_no_bare_crypto(self):
        """No goal prompt may contain bare crypto symbols — catches future additions."""
        for goal_key, prompt_text in GOAL_PROMPTS.items():
            for symbol in BARE_CRYPTO:
                assert not _word_boundaries(prompt_text, symbol), (
                    f"Bare crypto symbol '{symbol}' in goal '{goal_key}'. "
                    f"StockHistoricalDataClient returns wrong prices for crypto tickers. "
                    f"See docs/solutions/logic-errors/crypto-tickers-in-stock-client-prompt.md"
                )

    def test_goal_prompts_is_dict_with_expected_keys(self):
        """GOAL_PROMPTS covers all supported trading goals — catches accidental deletion."""
        expected = {
            "maximize_returns", "steady_income", "capital_preservation",
            "beat_sp500", "swing_trading", "passive_index",
        }
        assert set(GOAL_PROMPTS.keys()) == expected, (
            f"GOAL_PROMPTS keys changed. Expected {expected}, got {set(GOAL_PROMPTS.keys())}"
        )
