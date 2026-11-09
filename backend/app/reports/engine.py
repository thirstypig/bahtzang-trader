"""Weekly report (trading charter §5): did each portfolio beat SPY after all costs?

For each portfolio and the account overall, for the week (Mon–Fri ET) and since the
portfolio started:
  return vs SPY, before and after costs (spread, fees, Claude API, estimated tax),
  trades / wins / losses / average win and loss, cost breakdown, and every time a
  safety limit fired (counted from the trade ledger's reasons).

Alpaca paper fills market orders at the bid/ask (verified 2026-11-09 against quotes:
buys at the ask, sells at the bid), so the spread is ALREADY inside portfolio value —
it is recorded and shown, never subtracted again. Paper charges no regulatory fees, so
fees, the Claude bill and estimated tax are subtracted. Read-only over the portfolio ledger (reports → plans is
an allow-listed, read-only feature dependency).
"""

import json
import logging
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.costs import SHORT_TERM_TAX_RATE, BACKTEST_HALF_SPREAD_BPS, estimated_tax, realized_sells
from app.models import ApiUsage, Trade, record_api_usage
from app.plans.models import PlanSnapshot, Portfolio
from app.reports.models import WeeklyReport

logger = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")
NOTE_MODEL = "claude-sonnet-4-6"

GATE_WEEKS = 12  # charter §7 — a portfolio stays in the report this long after its last trade


def _net_shares(executed) -> float:
    net = 0.0
    for t in executed:
        if t.action == "buy":
            net += float(t.quantity)
        elif t.action == "sell":
            net -= float(t.quantity)
    return net


LIMIT_EVENT_PREFIXES = [
    "Daily loss halt", "Weekly loss halt", "Max holdings", "Max new buys",
    "Risk engine", "Broker stop fired", "HARD STOP", "Sell skipped",
]


def _utc_naive(d: date) -> datetime:
    """Midnight ET on ``d`` as naive UTC (how trade timestamps are stored)."""
    return datetime.combine(d, time.min, tzinfo=ET).astimezone(timezone.utc).replace(tzinfo=None)


def _close_on_or_before(closes: dict[date, float], d: date) -> float | None:
    eligible = [k for k in closes if k <= d]
    return closes[max(eligible)] if eligible else None


def _pct(end: float | None, start: float | None) -> float | None:
    if end is None or not start:
        return None
    return round((end / start - 1) * 100, 4)


def _snapshot_value(snap: PlanSnapshot, plan: Portfolio) -> float:
    # Budget changes move cash 1:1 (PATCH budget) — shift old values by the change.
    return float(snap.total_value) + (float(plan.budget) - float(snap.budget))


def _costs(db: Session, plan: Portfolio, trades: list[Trade], start: datetime, end: datetime,
           realized_by_id: dict) -> dict:
    executed = [t for t in trades if t.executed and t.action in ("buy", "sell")]
    spread = sum(float(t.spread_cost) for t in executed if t.spread_cost is not None)
    unpriced = sum(1 for t in executed if t.spread_cost is None)
    fees = sum(float(t.fee_cost) for t in executed if t.fee_cost is not None)
    api = sum(
        float(u.cost) for u in db.query(ApiUsage).filter(
            ApiUsage.portfolio_id == plan.id,
            ApiUsage.timestamp >= start.replace(tzinfo=timezone.utc),
            ApiUsage.timestamp < end.replace(tzinfo=timezone.utc),
        )
    )
    gains = [realized_by_id[t.id].gain for t in executed if t.id in realized_by_id]
    tax = estimated_tax(gains)
    return {
        "spread": round(spread, 4), "spread_unpriced_trades": unpriced,
        "spread_in_fills": True,  # paper fills at bid/ask: shown, not subtracted
        "fees": round(fees, 4), "api": round(api, 4), "est_tax": round(tax, 4),
        "total": round(fees + api + tax, 4),
        "realized_gain": round(sum(gains), 4),
    }


def _portfolio_row(db: Session, plan: Portfolio, week_ending: date, spy: dict) -> dict:
    monday = week_ending - timedelta(days=week_ending.weekday())
    w_start, w_end = _utc_naive(monday), _utc_naive(week_ending + timedelta(days=1))
    budget = float(plan.budget)

    before = (db.query(PlanSnapshot)
              .filter(PlanSnapshot.portfolio_id == plan.id, PlanSnapshot.date < monday)
              .order_by(PlanSnapshot.date.desc()).first())
    in_week = (db.query(PlanSnapshot)
               .filter(PlanSnapshot.portfolio_id == plan.id,
                       PlanSnapshot.date >= monday, PlanSnapshot.date <= week_ending)
               .order_by(PlanSnapshot.date.desc()).first())
    start_value = _snapshot_value(before, plan) if before else budget

    all_trades = (db.query(Trade)
                  .filter(Trade.portfolio_id == plan.id, Trade.timestamp < w_end)
                  .order_by(Trade.timestamp, Trade.id).all())
    executed_all = [t for t in all_trades if t.executed and t.action in ("buy", "sell")]

    end_estimated = False
    if in_week:
        end_value = _snapshot_value(in_week, plan)
    elif _net_shares(executed_all) <= 1e-9:
        # No shares held: value is just cash, which the ledger records exactly.
        cash = [t.virtual_cash_after for t in executed_all if t.virtual_cash_after is not None]
        end_value = float(cash[-1]) if cash else start_value
    else:
        end_value, end_estimated = start_value, True
    realized_by_id = {r.trade_id: r for r in realized_sells(executed_all)}
    week_trades = [t for t in all_trades if t.timestamp >= w_start]

    week_costs = _costs(db, plan, week_trades, w_start, w_end, realized_by_id)
    since_costs = _costs(db, plan, all_trades, datetime(1970, 1, 1), w_end, realized_by_id)

    week_sells = [realized_by_id[t.id] for t in week_trades if t.id in realized_by_id]
    wins = [s.gain for s in week_sells if s.gain > 0]
    losses = [s.gain for s in week_sells if s.gain < 0]

    events: dict[str, int] = {}
    for t in week_trades:
        for prefix in LIMIT_EVENT_PREFIXES:
            if (t.claude_reasoning or "").startswith(prefix) or (t.guardrail_block_reason or "").startswith(prefix):
                events[prefix] = events.get(prefix, 0) + 1
                break

    spy_week = _pct(_close_on_or_before(spy, week_ending), _close_on_or_before(spy, monday - timedelta(days=1)))
    created = plan.created_at.astimezone(ET).date() if plan.created_at.tzinfo else plan.created_at.date()
    spy_since = _pct(_close_on_or_before(spy, week_ending), _close_on_or_before(spy, created))

    after_week = round((end_value - start_value - week_costs["total"]) / start_value * 100, 4) if start_value else None
    after_since = round((end_value - budget - since_costs["total"]) / budget * 100, 4) if budget else None

    return {
        "id": plan.id, "name": plan.name, "active": plan.is_active,
        "start_value": round(start_value, 2), "end_value": round(end_value, 2),
        "end_value_estimated": end_estimated,
        "return_pct": _pct(end_value, start_value) or 0.0,
        "after_cost_return_pct": after_week,
        "spy_return_pct": spy_week,
        "beat_spy": (after_week > spy_week) if (after_week is not None and spy_week is not None) else None,
        "since_start": {
            "start_value": round(budget, 2),
            "return_pct": _pct(end_value, budget),
            "after_cost_return_pct": after_since,
            "spy_return_pct": spy_since,
            "costs": since_costs,
        },
        "trades": sum(1 for t in week_trades if t.executed and t.action in ("buy", "sell")),
        "wins": len(wins), "losses": len(losses),
        "win_rate": round(len(wins) / len(week_sells) * 100, 1) if week_sells else None,
        "avg_win": round(sum(wins) / len(wins), 2) if wins else None,
        "avg_loss": round(sum(losses) / len(losses), 2) if losses else None,
        "costs": week_costs,
        "limit_events": [{"type": k, "count": v} for k, v in events.items()],
    }


def _combine_costs(costs_list: list[dict], unassigned_api: float) -> dict:
    """Sum portfolio costs, then tax the NET realized gain once (one taxpayer: a loss
    in one portfolio offsets a gain in another) and add Claude cost no portfolio owns."""
    s = lambda k: sum(c[k] for c in costs_list)
    gain = s("realized_gain")
    tax = estimated_tax([gain])
    api = s("api") + unassigned_api
    return {
        "spread": round(s("spread"), 4), "spread_unpriced_trades": s("spread_unpriced_trades"),
        "spread_in_fills": True, "fees": round(s("fees"), 4), "api": round(api, 4),
        "est_tax": round(tax, 4), "total": round(s("fees") + api + tax, 4),
        "realized_gain": round(gain, 4),
    }


def _unassigned_api(db: Session, start: datetime, end: datetime) -> float:
    return sum(float(u.cost) for u in db.query(ApiUsage).filter(
        ApiUsage.portfolio_id.is_(None),
        ApiUsage.timestamp >= start.replace(tzinfo=timezone.utc),
        ApiUsage.timestamp < end.replace(tzinfo=timezone.utc),
    ))


def _account_row(db: Session, rows: list[dict], week_ending: date, spy: dict) -> dict:
    """All portfolios combined (NOT the Alpaca account: positions no portfolio owns
    are excluded)."""
    monday = week_ending - timedelta(days=week_ending.weekday())
    w_start, w_end = _utc_naive(monday), _utc_naive(week_ending + timedelta(days=1))
    start = sum(r["start_value"] for r in rows)
    end = sum(r["end_value"] for r in rows)
    costs = _combine_costs([r["costs"] for r in rows], _unassigned_api(db, w_start, w_end))
    since_costs = _combine_costs([r["since_start"]["costs"] for r in rows],
                                 _unassigned_api(db, datetime(1970, 1, 1), w_end))
    since_start_value = sum(r["since_start"]["start_value"] for r in rows)
    events: dict[str, int] = {}
    for r in rows:
        for e in r["limit_events"]:
            events[e["type"]] = events.get(e["type"], 0) + e["count"]
    spy_week = _pct(_close_on_or_before(spy, week_ending), _close_on_or_before(spy, monday - timedelta(days=1)))
    after = round((end - start - costs["total"]) / start * 100, 4) if start else None
    after_since = (round((end - since_start_value - since_costs["total"]) / since_start_value * 100, 4)
                   if since_start_value else None)
    return {
        "name": "All portfolios combined",
        "start_value": round(start, 2), "end_value": round(end, 2),
        "return_pct": _pct(end, start) or 0.0, "after_cost_return_pct": after,
        "spy_return_pct": spy_week,
        "beat_spy": (after > spy_week) if (after is not None and spy_week is not None) else None,
        "since_start_value": round(since_start_value, 2),
        "since_start": {
            "start_value": round(since_start_value, 2),
            "return_pct": _pct(end, since_start_value),
            "after_cost_return_pct": after_since,
            "spy_return_pct": None,  # portfolios start on different days — see each row
            "costs": since_costs,
        },
        "trades": sum(r["trades"] for r in rows),
        "wins": sum(r["wins"] for r in rows), "losses": sum(r["losses"] for r in rows),
        "costs": costs,
        "limit_events": [{"type": k, "count": v} for k, v in events.items()],
    }


def _included(db: Session, week_ending: date) -> list[Portfolio]:
    """Active portfolios, plus any that hold shares, traded or were snapshotted this
    week, or traded within the 12-week gate window — a switched-off portfolio must not
    drop out of the record (survivorship bias)."""
    monday = week_ending - timedelta(days=week_ending.weekday())
    w_start, w_end = _utc_naive(monday), _utc_naive(week_ending + timedelta(days=1))
    window_start = _utc_naive(monday - timedelta(weeks=GATE_WEEKS))
    touched = {pid for (pid,) in db.query(Trade.portfolio_id).filter(
        Trade.timestamp >= window_start, Trade.timestamp < w_end).distinct()}
    touched |= {pid for (pid,) in db.query(PlanSnapshot.portfolio_id).filter(
        PlanSnapshot.date >= monday, PlanSnapshot.date <= week_ending).distinct()}
    plans = db.query(Portfolio).order_by(Portfolio.id).all()
    out = []
    for p in plans:
        if float(p.budget) <= 0:
            continue
        if p.is_active or p.id in touched or _net_shares(
            db.query(Trade).filter(Trade.portfolio_id == p.id, Trade.executed.is_(True),
                                   Trade.timestamp < w_end).all()) > 1e-9:
            out.append(p)
    return out


def build_weekly_report(db: Session, week_ending: date, spy_closes: dict[date, float]) -> dict:
    rows = [_portfolio_row(db, p, week_ending, spy_closes) for p in _included(db, week_ending)]
    return {
        "week_ending": week_ending.isoformat(),
        "portfolios": rows,
        "account": _account_row(db, rows, week_ending, spy_closes),
        "assumptions": {
            "costs": "SEC/FINRA sell fees + Claude API + estimated tax are subtracted. The spread "
                     "(half the bid-ask gap at order time) is shown but not subtracted: paper fills "
                     "already happen at the bid/ask (verified 2026-11-09)",
            "combined_row": "sum of portfolios — excludes Alpaca positions no portfolio owns",
            "tax": f"{SHORT_TERM_TAX_RATE:.0%} of the period's net realized gain, floored at 0, no carry-forward",
            "backtest_half_spread_bps": BACKTEST_HALF_SPREAD_BPS,
            "pool_c": "OTC paper results look better than reality (paper ignores wide spreads)",
        },
    }


def last_friday(today: date | None = None) -> date:
    today = today or datetime.now(timezone.utc).astimezone(ET).date()
    return today - timedelta(days=(today.weekday() - 4) % 7)


async def _spy_closes(db: Session, start: date, end: date) -> dict[date, float]:
    from app.bars import fetch_and_cache_bars, load_bars
    await fetch_and_cache_bars(["SPY"], start, end, db)
    df = load_bars(["SPY"], start, end, db).get("SPY")
    if df is None:
        return {}
    return {(i.date() if hasattr(i, "date") else i): float(row["close"]) for i, row in df.iterrows()}


_NOTE_SYSTEM = (
    "You review a weekly paper-trading report for a small experiment whose only goal is to "
    "beat buy-and-hold SPY after all costs. Write a DRAFT 'what we learned / what we'd change' "
    "note for the human operator, who decides. Rules: at most 150 words; plain English; at most "
    "ONE rule change per portfolio, or 'no change'; base every claim on the numbers given; say "
    "when a week is too little data to conclude anything. No preamble."
)


async def _draft_note(payload: dict) -> tuple[str, object]:
    from app.claude_brain import client
    message = await client.messages.create(
        model=NOTE_MODEL,
        max_tokens=1200,
        system=_NOTE_SYSTEM,
        messages=[{"role": "user", "content": json.dumps(payload, default=str)}],
        timeout=60.0,
    )
    text = "".join(b.text for b in message.content if getattr(b, "type", "") == "text").strip()
    return text, getattr(message, "usage", None)


async def run_weekly_report(db: Session, week_ending: date | None = None) -> WeeklyReport:
    week_ending = week_ending or last_friday()
    created = [p.created_at for p in db.query(Portfolio).all() if p.created_at]
    first = min(created).date() if created else week_ending - timedelta(days=30)
    try:
        spy = await _spy_closes(db, first - timedelta(days=10), week_ending)
    except Exception as e:
        logger.warning("SPY closes unavailable for the weekly report: %s", e)
        spy = {}
    payload = build_weekly_report(db, week_ending, spy)

    note, note_model = None, None
    try:
        note, usage = await _draft_note(payload)
        note_model = NOTE_MODEL
        if usage is not None:
            record_api_usage(db, [usage], portfolio_id=None, purpose="report_note", model=NOTE_MODEL)
    except Exception as e:
        logger.warning("Weekly report note failed (report saved without it): %s", e)

    report = db.query(WeeklyReport).filter(WeeklyReport.week_ending == week_ending).first()
    if report is None:
        report = WeeklyReport(week_ending=week_ending, payload=payload)
        db.add(report)
    report.payload = payload
    report.note = note
    report.note_model = note_model
    report.created_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(report)
    return report
