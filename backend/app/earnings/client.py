"""Finnhub earnings calendar integration with aggressive caching."""

import logging
from datetime import date, timedelta

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.earnings.models import EarningsEvent

logger = logging.getLogger(__name__)

FINNHUB_BASE = "https://finnhub.io/api/v1"

_http_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=15.0)
    return _http_client


async def _fetch_earnings_calendar(from_date: date, to_date: date) -> list[dict]:
    """Fetch earnings calendar from Finnhub for a date range."""
    if not settings.FINNHUB_API_KEY:
        logger.warning("FINNHUB_API_KEY not set — skipping earnings fetch")
        return []

    client = _get_client()
    resp = await client.get(
        f"{FINNHUB_BASE}/calendar/earnings",
        params={
            "from": from_date.isoformat(),
            "to": to_date.isoformat(),
            "token": settings.FINNHUB_API_KEY,
        },
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("earningsCalendar", [])


async def refresh_earnings(db: Session, symbols: list[str]) -> int:
    """Fetch upcoming earnings and cache in DB.

    Uses 1 API call for the full 30-day calendar, then filters client-side.
    """
    today = date.today()

    try:
        all_events = await _fetch_earnings_calendar(today, today + timedelta(days=30))
    except Exception as e:
        logger.error("Finnhub earnings fetch failed: %s", e)
        return 0

    symbols_set = {s.upper() for s in symbols}
    relevant = [e for e in all_events if e.get("symbol", "").upper() in symbols_set]

    # Clear stale future data for these symbols
    db.query(EarningsEvent).filter(
        EarningsEvent.symbol.in_([s.upper() for s in symbols]),
        EarningsEvent.report_date >= today,
    ).delete(synchronize_session=False)

    count = 0
    for event in relevant:
        try:
            db.add(EarningsEvent(
                symbol=event["symbol"].upper(),
                report_date=date.fromisoformat(event["date"]),
                fiscal_quarter=f"Q{event.get('quarter', '?')} {event.get('year', '')}".strip(),
                eps_estimate=event.get("epsEstimate"),
                revenue_estimate=event.get("revenueEstimate"),
                hour=event.get("hour"),
            ))
            count += 1
        except (KeyError, ValueError) as e:
            logger.warning("Skipping malformed earnings event: %s", e)

    db.commit()
    logger.info("Cached %d earnings events for %d symbols", count, len(symbols))
    return count


def get_upcoming_earnings(
    db: Session,
    symbols: list[str] | None = None,
    days_ahead: int = 30,
) -> list[dict]:
    """Read cached earnings from DB. No API call."""
    today = date.today()
    cutoff = today + timedelta(days=days_ahead)

    query = db.query(EarningsEvent).filter(
        EarningsEvent.report_date >= today,
        EarningsEvent.report_date <= cutoff,
    )
    if symbols:
        query = query.filter(EarningsEvent.symbol.in_([s.upper() for s in symbols]))

    events = query.order_by(EarningsEvent.report_date).all()
    return [e.to_dict() for e in events]


def days_until_earnings(db: Session, symbol: str) -> int | None:
    """Days until the next earnings report. None if no upcoming earnings."""
    today = date.today()
    event = (
        db.query(EarningsEvent)
        .filter(
            EarningsEvent.symbol == symbol.upper(),
            EarningsEvent.report_date >= today,
        )
        .order_by(EarningsEvent.report_date)
        .first()
    )
    if event is None:
        return None
    return (event.report_date - today).days


def format_earnings_csv(db: Session, symbols: list[str]) -> str:
    """Format upcoming earnings as CSV for Claude's prompt."""
    events = get_upcoming_earnings(db, symbols, days_ahead=14)
    if not events:
        return ""

    today = date.today()
    header = "symbol,report_date,days_until,fiscal_qtr,eps_est,hour"
    rows = []
    for e in events:
        rd = date.fromisoformat(e["report_date"])
        days = (rd - today).days
        eps = str(e["eps_estimate"]) if e["eps_estimate"] is not None else "NaN"
        hour = e["hour"] or "unknown"
        rows.append(
            f"{e['symbol']},{e['report_date']},{days},"
            f"{e['fiscal_quarter'] or 'NaN'},{eps},{hour}"
        )

    return f"UPCOMING EARNINGS (next 14 days):\n{header}\n" + "\n".join(rows)
