"""APScheduler cron job: runs the trading pipeline on market days."""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from pytz import timezone

from app.database import SessionLocal
from app.guardrails import load_guardrails
from app.trade_executor import run_cycle

# Note: apply_schedule is imported by routes/guardrails.py for dynamic updates

logger = logging.getLogger(__name__)

ET = timezone("US/Eastern")

scheduler = AsyncIOScheduler()

# Schedule presets: (hour, minute) tuples for each frequency
FREQUENCY_SCHEDULES = {
    "1x": [(9, 35)],
    "3x": [(9, 35), (13, 0), (15, 45)],
    "5x": [(9, 35), (10, 30), (12, 0), (13, 30), (15, 0)],
}

# Job IDs are prefixed so we can find and remove them
JOB_PREFIX = "trading_cycle_"


async def _scheduled_cycle():
    """Run one trading cycle inside a fresh DB session."""
    logger.info("Scheduled trading cycle starting")
    db = SessionLocal()
    try:
        result = await run_cycle(db)
        logger.info("Cycle complete: %s", result)
    except Exception as e:
        logger.exception("Scheduled cycle failed: %s", e)
    finally:
        db.close()


def _remove_trading_jobs():
    """Remove all existing trading cycle jobs."""
    for job in scheduler.get_jobs():
        if job.id.startswith(JOB_PREFIX):
            scheduler.remove_job(job.id)


def apply_schedule(frequency: str):
    """Set up trading cycle jobs for the given frequency (1x, 3x, 5x)."""
    _remove_trading_jobs()

    times = FREQUENCY_SCHEDULES.get(frequency, FREQUENCY_SCHEDULES["1x"])

    for i, (hour, minute) in enumerate(times):
        trigger = CronTrigger(
            day_of_week="mon-fri",
            hour=hour,
            minute=minute,
            timezone=ET,
        )
        job_id = f"{JOB_PREFIX}{i}"
        scheduler.add_job(_scheduled_cycle, trigger, id=job_id)

    time_strs = [f"{h}:{m:02d}" for h, m in times]
    logger.info("Schedule updated: %s/day at %s ET", frequency, ", ".join(time_strs))


def start_scheduler():
    """Start the APScheduler with the configured trading frequency."""
    scheduler.start()

    # Read frequency from DB using a temporary session
    db = SessionLocal()
    try:
        config = load_guardrails(db)
        frequency = config.get("trading_frequency", "1x")
    finally:
        db.close()

    apply_schedule(frequency)


def stop_scheduler():
    """Shut down the scheduler gracefully."""
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")
