"""Unit and integration tests for app.guardrails — risk presets, validation, DB ops."""

import pytest
from pydantic import ValidationError

from app.guardrails import (
    RISK_PRESETS,
    TRADING_GOALS,
    VALID_GOALS,
    GuardrailsUpdate,
    apply_risk_preset,
    load_guardrails,
    save_guardrails,
)
from app.models import GuardrailsConfig


# ---------------------------------------------------------------------------
# Unit tests — no DB required
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestApplyRiskPreset:
    """apply_risk_preset returns guardrail values scaled to portfolio value."""

    def test_conservative_values(self):
        result = apply_risk_preset("conservative", 100_000)
        assert result["risk_profile"] == "conservative"
        assert result["max_total_invested"] == 30_000     # 30% of 100k
        assert result["max_single_trade_size"] == 5_000   # 5% of 100k
        assert result["stop_loss_threshold"] == 0.03
        assert result["daily_order_limit"] == 3
        assert result["min_confidence"] == 0.75
        assert result["max_positions"] == 5
        assert result["kill_switch"] is False

    def test_moderate_values(self):
        result = apply_risk_preset("moderate", 100_000)
        assert result["risk_profile"] == "moderate"
        assert result["max_total_invested"] == 60_000     # 60%
        assert result["max_single_trade_size"] == 10_000  # 10%
        assert result["stop_loss_threshold"] == 0.05
        assert result["daily_order_limit"] == 5
        assert result["min_confidence"] == 0.60
        assert result["max_positions"] == 10

    def test_aggressive_values(self):
        result = apply_risk_preset("aggressive", 100_000)
        assert result["risk_profile"] == "aggressive"
        assert result["max_total_invested"] == 90_000     # 90%
        assert result["max_single_trade_size"] == 20_000  # 20%
        assert result["stop_loss_threshold"] == 0.08
        assert result["daily_order_limit"] == 10
        assert result["min_confidence"] == 0.45
        assert result["max_positions"] == 20

    def test_scales_to_portfolio_value(self):
        """Dollar amounts should scale linearly with portfolio value."""
        small = apply_risk_preset("moderate", 50_000)
        large = apply_risk_preset("moderate", 200_000)
        assert large["max_total_invested"] == small["max_total_invested"] * 4
        assert large["max_single_trade_size"] == small["max_single_trade_size"] * 4

    def test_unknown_profile_defaults_to_moderate(self):
        """Unknown profile name falls back to moderate preset."""
        result = apply_risk_preset("unknown_profile", 100_000)
        moderate = apply_risk_preset("moderate", 100_000)
        # Dollar amounts and limits should match moderate
        assert result["max_total_invested"] == moderate["max_total_invested"]
        assert result["daily_order_limit"] == moderate["daily_order_limit"]
        # But the profile string is the one passed in
        assert result["risk_profile"] == "unknown_profile"

    def test_default_portfolio_value(self):
        """Default portfolio_value is 100_000."""
        result = apply_risk_preset("conservative")
        assert result["max_total_invested"] == 30_000

    def test_returns_all_expected_keys(self):
        result = apply_risk_preset("moderate")
        expected_keys = {
            "risk_profile", "trading_goal", "trading_frequency",
            "max_total_invested", "max_single_trade_size",
            "stop_loss_threshold", "daily_order_limit",
            "min_confidence", "max_positions", "kill_switch",
        }
        assert set(result.keys()) == expected_keys


@pytest.mark.unit
class TestValidGoals:
    """VALID_GOALS and TRADING_GOALS contain all 6 trading goals."""

    def test_trading_goals_has_six_entries(self):
        assert len(TRADING_GOALS) == 6

    def test_valid_goals_contains_all_goal_keys(self):
        expected = {
            "maximize_returns",
            "steady_income",
            "capital_preservation",
            "beat_sp500",
            "swing_trading",
            "passive_index",
        }
        assert set(TRADING_GOALS.keys()) == expected

    def test_valid_goals_is_pipe_separated_string(self):
        """VALID_GOALS is a pipe-joined string used in regex patterns."""
        goals = VALID_GOALS.split("|")
        assert len(goals) == 6
        for goal in goals:
            assert goal in TRADING_GOALS


@pytest.mark.unit
class TestGuardrailsUpdateValidation:
    """GuardrailsUpdate Pydantic model validates allowed fields."""

    def test_accepts_valid_risk_profile(self):
        for profile in ("conservative", "moderate", "aggressive"):
            update = GuardrailsUpdate(risk_profile=profile)
            assert update.risk_profile == profile

    def test_rejects_invalid_risk_profile(self):
        with pytest.raises(ValidationError):
            GuardrailsUpdate(risk_profile="yolo")

    def test_accepts_valid_trading_goal(self):
        update = GuardrailsUpdate(trading_goal="beat_sp500")
        assert update.trading_goal == "beat_sp500"

    def test_rejects_invalid_trading_goal(self):
        with pytest.raises(ValidationError):
            GuardrailsUpdate(trading_goal="get_rich_quick")

    def test_accepts_valid_trading_frequency(self):
        for freq in ("1x", "3x", "5x"):
            update = GuardrailsUpdate(trading_frequency=freq)
            assert update.trading_frequency == freq

    def test_rejects_invalid_trading_frequency(self):
        with pytest.raises(ValidationError):
            GuardrailsUpdate(trading_frequency="10x")

    def test_accepts_valid_dollar_amounts(self):
        update = GuardrailsUpdate(
            max_total_invested=50_000,
            max_single_trade_size=5_000,
        )
        assert update.max_total_invested == 50_000
        assert update.max_single_trade_size == 5_000

    def test_rejects_negative_amounts(self):
        with pytest.raises(ValidationError):
            GuardrailsUpdate(max_total_invested=-100)

    def test_rejects_zero_amounts(self):
        with pytest.raises(ValidationError):
            GuardrailsUpdate(max_single_trade_size=0)

    def test_accepts_stop_loss_in_range(self):
        update = GuardrailsUpdate(stop_loss_threshold=0.05)
        assert update.stop_loss_threshold == 0.05

    def test_rejects_stop_loss_out_of_range(self):
        with pytest.raises(ValidationError):
            GuardrailsUpdate(stop_loss_threshold=1.0)  # must be < 1

    def test_accepts_all_none_fields(self):
        """All fields are optional — empty update is valid."""
        update = GuardrailsUpdate()
        assert update.risk_profile is None
        assert update.trading_goal is None

    def test_accepts_valid_target_date(self):
        update = GuardrailsUpdate(target_date="2026-12-31")
        assert update.target_date == "2026-12-31"

    def test_rejects_invalid_target_date_format(self):
        with pytest.raises(ValidationError):
            GuardrailsUpdate(target_date="12/31/2026")

    def test_no_kill_switch_field(self):
        """kill_switch is deliberately excluded from GuardrailsUpdate."""
        update = GuardrailsUpdate()
        assert not hasattr(update, "kill_switch") or "kill_switch" not in update.model_fields


# ---------------------------------------------------------------------------
# Integration tests — require db_session fixture (SQLite in-memory)
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestLoadGuardrails:
    """load_guardrails reads config from DB, creating defaults if empty."""

    def test_returns_default_config_on_empty_db(self, db_session):
        """First call creates a default GuardrailsConfig row."""
        result = load_guardrails(db_session)
        assert isinstance(result, dict)
        assert result["risk_profile"] == "moderate"
        assert result["trading_goal"] == "maximize_returns"
        assert result["trading_frequency"] == "1x"
        assert result["kill_switch"] is False
        assert result["max_positions"] == 5
        assert result["min_confidence"] == 0.60

    def test_returns_existing_config(self, db_session):
        """If a row already exists, it returns that row's values."""
        # Create config with custom values
        config = GuardrailsConfig(id=1, risk_profile="aggressive", daily_order_limit=10)
        db_session.add(config)
        db_session.commit()

        result = load_guardrails(db_session)
        assert result["risk_profile"] == "aggressive"
        assert result["daily_order_limit"] == 10

    def test_returns_all_expected_keys(self, db_session):
        result = load_guardrails(db_session)
        expected_keys = {
            "risk_profile", "trading_goal", "trading_frequency",
            "max_total_invested", "max_single_trade_size",
            "stop_loss_threshold", "daily_order_limit",
            "min_confidence", "max_positions", "kill_switch",
            "kelly_fraction", "circuit_breaker_daily_pct",
            "circuit_breaker_weekly_pct", "respect_wash_sale",
            "pdt_protection",
        }
        assert set(result.keys()) == expected_keys


@pytest.mark.integration
class TestSaveGuardrails:
    """save_guardrails persists changes and returns the updated config."""

    def test_updates_single_field(self, db_session):
        result = save_guardrails(db_session, {"risk_profile": "aggressive"})
        assert result["risk_profile"] == "aggressive"

    def test_updates_multiple_fields(self, db_session):
        updates = {
            "risk_profile": "conservative",
            "daily_order_limit": 3,
            "min_confidence": 0.80,
        }
        result = save_guardrails(db_session, updates)
        assert result["risk_profile"] == "conservative"
        assert result["daily_order_limit"] == 3
        assert result["min_confidence"] == 0.80

    def test_persists_to_database(self, db_session):
        """Changes should be visible on a subsequent load."""
        save_guardrails(db_session, {"max_positions": 15})
        loaded = load_guardrails(db_session)
        assert loaded["max_positions"] == 15

    def test_ignores_unknown_fields(self, db_session):
        """Fields not on GuardrailsConfig are silently ignored."""
        result = save_guardrails(db_session, {"nonexistent_field": 999})
        # Should return valid config without error
        assert "risk_profile" in result
        assert "nonexistent_field" not in result

    def test_returns_full_config_dict(self, db_session):
        result = save_guardrails(db_session, {"risk_profile": "moderate"})
        assert isinstance(result, dict)
        # Should have all config keys, not just the updated one
        assert "kill_switch" in result
        assert "min_confidence" in result

    def test_toggle_kill_switch(self, db_session):
        """kill_switch can be toggled via save_guardrails (used by /killswitch route)."""
        result = save_guardrails(db_session, {"kill_switch": True})
        assert result["kill_switch"] is True
        result = save_guardrails(db_session, {"kill_switch": False})
        assert result["kill_switch"] is False
