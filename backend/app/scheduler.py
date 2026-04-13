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


SNAPSHOT_JOB_ID = "daily_snapshot"


async def _take_snapshot():
    """Capture end-of-day portfolio state and SPY close."""
    from datetime import date as date_type

    logger.info("Taking daily portfolio snapshot")
    db = SessionLocal()
    try:
        from app.brokers.alpaca import AlpacaBroker
        from app.models import PortfolioSnapshot

        broker = AlpacaBroker()
        balance = await broker.get_account_balance("default")
        positions = await broker.get_positions("default")

        invested = sum(p.get("marketValue", 0) for p in positions)
        unrealized = sum(p.get("currentDayProfitLoss", 0) for p in positions)

        # Get SPY close via Alpaca Data API
        spy_close = None
        try:
            from alpaca.data.historical import StockHistoricalDataClient
            from alpaca.data.requests import StockBarsRequest
            from alpaca.data.timeframe import TimeFrame
            from app.config import settings
            import asyncio
            from datetime import timedelta

            data_client = StockHistoricalDataClient(
                settings.ALPACA_API_KEY, settings.ALPACA_SECRET_KEY
            )
            today = date_type.today()
            bars = await asyncio.to_thread(
                data_client.get_stock_bars,
                StockBarsRequest(
                    symbol_or_symbols="SPY",
                    timeframe=TimeFrame.Day,
                    start=today - timedelta(days=5),
                    end=today,
                ),
            )
            spy_bars = bars.get("SPY", bars.data.get("SPY", []))
            if spy_bars:
                spy_close = float(spy_bars[-1].close)
        except Exception as e:
            logger.warning("Failed to fetch SPY close: %s", e)

        today = date_type.today()
        snapshot = PortfolioSnapshot(
            date=today,
            total_equity=balance["total_value"],
            cash=balance["cash_available"],
            invested=invested,
            unrealized_pnl=unrealized,
            spy_close=spy_close,
        )
        db.merge(snapshot)
        db.commit()
        logger.info(
            "Snapshot saved: equity=$%.2f, SPY=$%.2f",
            balance["total_value"],
            spy_close or 0,
        )
    except Exception as e:
        logger.exception("Snapshot failed: %s", e)
    finally:
        db.close()


EARNINGS_JOB_ID = "daily_earnings_refresh"


async def _refresh_earnings():
    """Fetch upcoming earnings for all held symbols."""
    logger.info("Refreshing earnings calendar")
    db = SessionLocal()
    try:
        from app.brokers.alpaca import AlpacaBroker
        from app.earnings.client import refresh_earnings

        b = AlpacaBroker()
        positions = await b.get_positions("default")
        symbols = [p.get("instrument", {}).get("symbol", "") for p in positions]
        symbols = [s for s in symbols if s]

        if symbols:
            count = await refresh_earnings(db, symbols)
            logger.info("Earnings refresh: %d events for %d symbols", count, len(symbols))
        else:
            logger.info("No positions — skipping earnings refresh")
    except Exception as e:
        logger.exception("Earnings refresh failed: %s", e)
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

    # Daily snapshot at 4:05 PM ET (after market close settles)
    snapshot_trigger = CronTrigger(
        day_of_week="mon-fri",
        hour=16, minute=5,
        timezone=ET,
    )
    scheduler.add_job(
        _take_snapshot, snapshot_trigger,
        id=SNAPSHOT_JOB_ID, replace_existing=True,
    )

    # Daily earnings refresh at 7:00 AM ET (before first trading cycle)
    earnings_trigger = CronTrigger(
        day_of_week="mon-fri",
        hour=7, minute=0,
        timezone=ET,
    )
    scheduler.add_job(
        _refresh_earnings, earnings_trigger,
        id=EARNINGS_JOB_ID, replace_existing=True,
    )

    # Daily summary at 4:10 PM ET (after snapshot)
    summary_trigger = CronTrigger(
        day_of_week="mon-fri",
        hour=16, minute=10,
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
