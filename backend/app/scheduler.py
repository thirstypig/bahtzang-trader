"""APScheduler cron job: runs the trading pipeline on market days."""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from pytz import timezone

from app.database import SessionLocal
from app.guardrails import load_guardrails
from app.models import Trade
from app import notifier
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


async def _daily_summary():
    """Send end-of-day summary notification."""
    from datetime import datetime, timezone
    logger.info("Sending daily summary")
    db = SessionLocal()
    try:
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        today_trades = (
            db.query(Trade)
            .filter(Trade.timestamp >= today_start)
            .all()
        )

        executed = sum(1 for t in today_trades if t.executed)
        blocked = sum(1 for t in today_trades if not t.guardrail_passed and t.action != "hold")
        holds = sum(1 for t in today_trades if t.action == "hold")

        # Get portfolio value from broker
        from app.brokers.alpaca import AlpacaBroker
        broker = AlpacaBroker()
        balance = await broker.get_account_balance("default")

        await notifier.notify_daily_summary(
            trades_executed=executed,
            trades_blocked=blocked,
            holds=holds,
            portfolio_value=balance["total_value"],
            daily_pnl=0,  # TODO: compute from snapshots once Phase B is built
        )
    except Exception as e:
        logger.exception("Daily summary failed: %s", e)
    finally:
        db.close()


SUMMARY_JOB_ID = "daily_summary"


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

    # Daily summary at 4:05 PM ET
    summary_trigger = CronTrigger(
        day_of_week="mon-fri",
        hour=16, minute=5,
        timezone=ET,
    )
    scheduler.add_job(
        _daily_summary, summary_trigger,
        id=SUMMARY_JOB_ID, replace_existing=True,
    )


def stop_scheduler():
    """Shut down the scheduler gracefully."""
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")
