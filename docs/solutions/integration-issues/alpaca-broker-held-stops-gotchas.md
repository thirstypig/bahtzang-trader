---
id: DOC-055
type: solution
status: active
phase: G
owner: james
tags: [trading-pipeline, risk, market-data]
links: [DOC-054, PRD-002, DOC-053]
updated: 2026-11-09
description: Alpaca behaviours verified live while wiring broker-held stops into a shared paper account (PRs #44–#54) — stop-leg TIF, async cancels, paper fill prices, late-seen stop fills, an alpaca-py asset-parse crash, and why OTC was dropped.
severity: medium
component: brokers/alpaca, plans/stops, costs, reports
legacy_type: integration-issue
---

# Alpaca broker-held stops: gotchas found wiring them in

Every item below was checked against the live paper account or the installed SDK, not
assumed. The code that relies on each is named so a future change knows what it breaks.

## 1. The OTO stop leg must be GTC, not DAY

A DAY stop leg expires at the close and leaves the position unprotected overnight. Send the
OTO parent with `time_in_force=GTC` so the leg inherits it. The leg's order id is
`order.legs[0].id` on the submit response. Proven end to end on 10/20, when a 1-share F test's
GTC stop fired at $11.57. → `AlpacaBroker.place_order` (PR #44).

## 2. Cancels are asynchronous, and can lose a race with a fill

- `cancel_order_by_id` returns before the cancel settles: the order sits in
  `pending_cancel` for a moment, and a sell sent then is **rejected** because the shares are
  still reserved by the stop. Poll `get_order` until the status leaves `pending_cancel`.
- If the stop already filled, Alpaca refuses the cancel (`42210000 order is not cancelable`).
  Report `"filled"` so the caller records the fill instead of selling shares that are gone.

→ `AlpacaBroker.cancel_order`, `plans/stops.release_stops`.

## 3. Paper market orders fill at the bid/ask

Verified 2026-11-09: paper fills happen at the quoted bid (sells) or ask (buys), not the
midpoint. The spread is therefore **already inside portfolio value**. The weekly report
records each trade's half-spread (`Trade.spread_cost`) and shows it, but must not subtract it
again. Doing so double-counts the cost. The backtester has no real fills, so it does charge a
5 bps half-spread. → `app/costs.py`, `app/reports/engine.py`.

## 4. A stop fill is seen late, so use the broker's fill time

`reconcile_stops` runs at the start of the next cycle, so a stop that fires Friday at 2:45 PM
is only noticed on Monday morning. Stamping the sell with `now()` moved it into the wrong
weekly report. Since PR #54, `get_order` returns Alpaca's `filled_at` (tz-aware UTC) and
`_record_fill` uses it, falling back to now. → `plans/stops._record_fill`.

## 5. alpaca-py 0.43 `get_all_assets` crashes on the TXSE exchange

The SDK's `Asset` model has a closed exchange enum. Assets listed on the new Texas Stock
Exchange (`TXSE`) fail validation and the whole call raises. Work around it by reading the raw
JSON (`raw_data=True` on the client) for asset listings until the SDK adds the value.

## 6. Why OTC was dropped

Alpaca's tradable OTC list is about 310 names, nearly all foreign blue-chip ADRs, not small
companies. Our market-data plan also can't quote OTC, so the risk engine couldn't size or stop
those trades. Pools A/B/C were dropped from the charter on 2026-11-09 (DOC-054).

## Related decision: account-wide breaker retired (PR #54)

All portfolios share one Alpaca account. A breaker that measures the **whole account** also
reacts to positions no portfolio owns. The old `circuit_breaker.py` switched off every
portfolio on a 5%/day or 10%/week account drop, with no Slack alert. It was retired in favour
of the per-portfolio charter §3 limits (`plans/limits.py`), which alert on every halt. In a
shared account, use per-portfolio safety limits only.
