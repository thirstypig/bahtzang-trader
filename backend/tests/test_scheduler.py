"""Scheduler — execution window and exit-only wiring.

Guards:
  - First slot for every frequency preset is 10:00 AM ET (not the old 9:35)
  - EXIT_CHECK_JOB_ID constant is stable (APScheduler uses it to dedup the job)
  - _scheduled_cycle(exit_only=True) propagates the flag to run_all_plans
  - _scheduled_cycle skips gracefully when there are no active portfolios
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.scheduler import FREQUENCY_SCHEDULES, EXIT_CHECK_JOB_ID, _extract_latest_close


class _FakeBar:
    def __init__(self, close):
        self.close = close


class _FakeBarSet:
    """Mimics Alpaca's BarSet: per-symbol lists on .data, and crucially NO .get()."""

    def __init__(self, data):
        self.data = data


@pytest.mark.unit
class TestExtractLatestClose:
    def test_returns_latest_close_from_barset_data(self):
        bars = _FakeBarSet({"SPY": [_FakeBar(500.0), _FakeBar(512.34)]})
        assert _extract_latest_close(bars, "SPY") == 512.34

    def test_returns_none_when_symbol_absent(self):
        assert _extract_latest_close(_FakeBarSet({}), "SPY") is None

    def test_returns_none_when_no_bars(self):
        assert _extract_latest_close(_FakeBarSet({"SPY": []}), "SPY") is None

    def test_does_not_call_get_on_the_barset(self):
        # Regression: old code did bars.get("SPY", ...) — BarSet has no .get(),
        # which raised 'BarSet object has no attribute get' and logged SPY=$0.00.
        bars = _FakeBarSet({"SPY": [_FakeBar(123.45)]})
        assert not hasattr(bars, "get")  # our fake matches the real BarSet
        assert _extract_latest_close(bars, "SPY") == 123.45


@pytest.mark.unit
class TestFrequencySchedules:
    def test_all_presets_start_at_10am(self):
        for freq, slots in FREQUENCY_SCHEDULES.items():
            first_hour, first_minute = slots[0]
            assert (first_hour, first_minute) == (10, 0), (
                f"Preset '{freq}' first slot is {first_hour}:{first_minute:02d}, expected 10:00"
            )

    def test_slot_counts_match_frequency_names(self):
        assert len(FREQUENCY_SCHEDULES["1x"]) == 1
        assert len(FREQUENCY_SCHEDULES["3x"]) == 3
        assert len(FREQUENCY_SCHEDULES["5x"]) == 5

    def test_no_slot_before_market_open(self):
        for freq, slots in FREQUENCY_SCHEDULES.items():
            for hour, minute in slots:
                assert hour >= 9 and (hour > 9 or minute >= 30), (
                    f"Preset '{freq}' has slot at {hour}:{minute:02d} — before 9:30 market open"
                )

    def test_exit_check_job_id_is_stable(self):
        assert EXIT_CHECK_JOB_ID == "daily_exit_check"


@pytest.mark.asyncio
@pytest.mark.unit
class TestScheduledCycle:
    async def test_exit_only_flag_propagated_to_run_all_plans(self, db_session):
        from app.scheduler import _scheduled_cycle

        mock_portfolio = MagicMock()
        mock_portfolio.is_active = True

        with patch("app.scheduler.SessionLocal", return_value=db_session), \
             patch("app.plans.models.Portfolio") as mock_model, \
             patch("app.plans.executor.run_all_plans", new=AsyncMock(return_value=[])) as mock_run:

            db_session.query = MagicMock()
            db_session.query.return_value.filter.return_value.count.return_value = 1

            await _scheduled_cycle(exit_only=True)

        mock_run.assert_awaited_once()
        _, kwargs = mock_run.call_args
        assert kwargs.get("exit_only") is True or mock_run.call_args.args[1] is True

    async def test_normal_cycle_passes_exit_only_false(self, db_session):
        from app.scheduler import _scheduled_cycle

        with patch("app.scheduler.SessionLocal", return_value=db_session), \
             patch("app.plans.executor.run_all_plans", new=AsyncMock(return_value=[])) as mock_run:

            db_session.query = MagicMock()
            db_session.query.return_value.filter.return_value.count.return_value = 1

            await _scheduled_cycle(exit_only=False)

        mock_run.assert_awaited_once()
        _, kwargs = mock_run.call_args
        exit_only_arg = kwargs.get("exit_only", mock_run.call_args.args[1] if len(mock_run.call_args.args) > 1 else False)
        assert exit_only_arg is False

    async def test_skips_when_no_active_portfolios(self, db_session):
        from app.scheduler import _scheduled_cycle

        with patch("app.scheduler.SessionLocal", return_value=db_session), \
             patch("app.plans.executor.run_all_plans", new=AsyncMock()) as mock_run:

            db_session.query = MagicMock()
            db_session.query.return_value.filter.return_value.count.return_value = 0

            await _scheduled_cycle()

        mock_run.assert_not_awaited()
