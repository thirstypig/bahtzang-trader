import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from pytz import timezone

from app.database import SessionLocal
from app.trade_executor import run_cycle

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

# US market days: Monday–Friday, 9:35 AM Eastern
# (5 minutes after open to let initial volatility settle)
MARKET_TRIGGER = CronTrigger(
    day_of_week="mon-fri",
    hour=9,
    minute=35,
    timezone=timezone("US/Eastern"),
)


async def _scheduled_cycle():
    """Run one trading cycle inside a fresh DB session."""
    logger.info("Scheduled trading cycle starting")
    db = SessionLocal()
    try:
        result = await run_cycle(db)
        logger.info("Cycle complete: %s", result)
    except Exception as e:
        logger.error("Scheduled cycle failed: %s", e)
    finally:
        db.close()


def start_scheduler():
    """Start the APScheduler cron job."""
    scheduler.add_job(_scheduled_cycle, MARKET_TRIGGER, id="trading_cycle")
    scheduler.start()
    logger.info("Scheduler started — next run at 9:35 AM ET on market days")


def stop_scheduler():
    """Shut down the scheduler gracefully."""
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")
