"""APScheduler cron job: runs the trading pipeline on market days.

Portfolio-only model: every cycle iterates active portfolios and runs each
one's executor with its own strategy. There is no global trader; if no
portfolios are active, the scheduler logs and skips.
"""

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from pytz import timezone

from app.database import SessionLocal
from app.models import Trade
from app import notifier

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
    """Run one trading cycle — iterate every active portfolio."""
    logger.info("Scheduled trading cycle starting")
    db = SessionLocal()
    try:
        from app.plans.models import Portfolio
        active = db.query(Portfolio).filter(Portfolio.is_active.is_(True)).count()
        if active == 0:
            logger.info("No active portfolios — skipping cycle")
            return
        from app.plans.executor import run_all_plans
        results = await run_all_plans(db)
        logger.info("Cycle complete: %d portfolios processed", len(results))
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
        # 040-fix: Run sync DB query in thread to avoid blocking event loop
        today_trades = await asyncio.to_thread(
            lambda: db.query(Trade).filter(Trade.timestamp >= today_start).all()
        )

        executed = sum(1 for t in today_trades if t.executed)
        blocked = sum(1 for t in today_trades if not t.guardrail_passed and t.action != "hold")
        holds = sum(1 for t in today_trades if t.action == "hold")

        # Get portfolio value from broker
        from app.brokers.alpaca import AlpacaBroker
        from app.models import PortfolioSnapshot
        broker = AlpacaBroker()
        balance = await broker.get_account_balance("default")

        # Compute daily P&L: diff the two most recent snapshots.
        # The snapshot job runs at 4:05 PM; this summary runs at 4:10 PM,
        # so today's snapshot is already committed when we query here.
        snapshots = await asyncio.to_thread(
            lambda: db.query(PortfolioSnapshot)
            .order_by(PortfolioSnapshot.date.desc())
            .limit(2)
            .all()
        )
        daily_pnl = (
            float(snapshots[0].total_equity) - float(snapshots[1].total_equity)
            if len(snapshots) >= 2
            else 0.0
        )

        await notifier.notify_daily_summary(
            trades_executed=executed,
            trades_blocked=blocked,
            holds=holds,
            portfolio_value=balance["total_value"],
            daily_pnl=daily_pnl,
        )
    except Exception as e:
        logger.exception("Daily summary failed: %s", e)
    finally:
        db.close()


PLAN_SNAPSHOT_JOB_ID = "daily_plan_snapshots"


async def _take_plan_snapshots():
    """Capture end-of-day portfolio state for each active plan."""
    logger.info("Taking daily plan snapshots")
    db = SessionLocal()
    try:
        from app.plans.snapshots import take_plan_snapshots

        count = await take_plan_snapshots(db)
        logger.info("Plan snapshots complete: %d plans captured", count)
    except Exception as e:
        logger.exception("Plan snapshots failed: %s", e)
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
        # 040-fix: Run sync DB write in thread to avoid blocking event loop
        await asyncio.to_thread(lambda: (db.merge(snapshot), db.commit()))
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


SCREENER_JOB_ID = "daily_screener"


async def _run_screener():
    """Refresh the screener's ranked candidates (advisory — does not trade)."""
    logger.info("Running daily screener")
    db = SessionLocal()
    try:
        from app.screener.engine import run_screener

        run = await run_screener(db)
        logger.info("Screener done: status=%s, %d candidates", run.status, run.scored_count)
    except Exception as e:
        logger.exception("Daily screener failed: %s", e)
    finally:
        db.close()


SUMMARY_JOB_ID = "daily_summary"


def _max_frequency_among_active(db) -> str:
    """Pick the highest frequency among active portfolios.

    Portfolio-only model: there is no global frequency. The scheduler runs
    at the most aggressive cadence any active portfolio asks for, and each
    portfolio's own cooldown/frequency caps prevent over-trading. Falls
    back to "1x" when no portfolios are active.
    """
    from app.plans.models import Portfolio
    rank = {"1x": 1, "3x": 3, "5x": 5}
    portfolios = db.query(Portfolio).filter(Portfolio.is_active.is_(True)).all()
    if not portfolios:
        return "1x"
    return max(portfolios, key=lambda p: rank.get(p.trading_frequency, 1)).trading_frequency


def start_scheduler():
    """Start the APScheduler at the most-aggressive frequency among portfolios."""
    scheduler.start()
    db = SessionLocal()
    try:
        apply_schedule(_max_frequency_among_active(db))
    finally:
        db.close()

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

    # Daily plan snapshots at 4:06 PM ET (right after global snapshot)
    plan_snapshot_trigger = CronTrigger(
        day_of_week="mon-fri",
        hour=16, minute=6,
        timezone=ET,
    )
    scheduler.add_job(
        _take_plan_snapshots, plan_snapshot_trigger,
        id=PLAN_SNAPSHOT_JOB_ID, replace_existing=True,
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

    # Daily screener refresh at 7:30 AM ET (after earnings, before first cycle)
    screener_trigger = CronTrigger(
        day_of_week="mon-fri",
        hour=7, minute=30,
        timezone=ET,
    )
    scheduler.add_job(
        _run_screener, screener_trigger,
        id=SCREENER_JOB_ID, replace_existing=True,
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
