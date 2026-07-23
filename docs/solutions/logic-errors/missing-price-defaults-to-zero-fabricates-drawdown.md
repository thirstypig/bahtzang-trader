---
id: DOC-052
type: solution
status: active
phase: G
owner: james
tags: [market-data, risk, database]
links: [DOC-017, DOC-018, PRD-002]
updated: 2026-07-22
description: Daily portfolio snapshots valued any position with a missing price at $0, fabricating a -40.8% drawdown on a portfolio that was actually down 7.5%. Root cause was a `.get(ticker, 0)` price default fed by a quote source that silently drops failed tickers.
severity: high
component: plans/snapshots, market_data, plan_snapshots table
legacy_type: logic-error
---

# Missing price defaults to $0, fabricating a portfolio drawdown

## Problem

The dashboard reported Test 5 (portfolio id 6) down **-40.8%**. Reconstructing the
portfolio from the trade ledger and valuing it at real Alpaca closes showed it was
actually down **-7.5%**. Every stored `plan_snapshots` row was wrong — by up to **$4,156
on a single day** — and one fully-invested day (2026-07-09) was logged with
`invested_value = $0.00`.

This is not a display bug. `plan_snapshots` feeds the **Phase G zero-losing-weeks gate**,
so the corruption made the graduation criterion unmeasurable and would have failed the
portfolio for a collapse it never suffered.

### Symptoms

- Equity curve swinging ±$1,800 on days with **zero trades** (impossible from real P&L).
- `invested_value` far below the known cost basis of open positions; occasionally `$0`.
- The reported loss (-40.8%) wildly exceeded the sum of realised + unrealised P&L.
- No errors, no exceptions, no logs. The job "succeeded" every day.

## Investigation

1. **Reconstructed holdings from the ledger.** Summed executed buys/sells per ticker for
   portfolio 6 → 5 open positions (DVA, MPC, FTNT, PNC, PANW), cost basis ~$4,239, plus
   $4,958 cash = ~$9,197. Nowhere near the stored $5,920.
2. **Valued them at live Alpaca prices** → $9,250 (-7.5%). A completely independent path
   (Alpaca `get_stock_latest_bar`) confirmed the true number, ruling out a ledger error.
3. **Compared stored `invested_value` to reconstruction** day by day. On 2026-07-21 the
   snapshot recorded $962 invested — exactly the value of **one** position (DVA). The
   other four were missing entirely, as if worth $0.
4. **Read `snapshots.py`.** Found `qty * price_map.get(ticker, 0)` — a missing price
   silently becomes $0.
5. **Traced `price_map`'s source:** `market_data.get_quotes()`, whose own docstring says
   it *"drops failed tickers"* and that they are *"backfilled from Alpaca bars in the
   executor's indicator-patch step."* The executor patches around this; **snapshots was
   the one consumer left on the raw, unpatched path.**

## Root cause

Two independent faults compounded into a silent one:

1. **`.get(ticker, 0)` makes "unknown" and "worthless" the same value.** A price that
   could not be fetched fell through to `0` and flowed straight into P&L arithmetic as if
   the position were worthless.

2. **The quote source fails silently in two ways, both landing on $0:**
   - `get_quotes()` runs per-ticker requests with `return_exceptions=True` and **drops**
     any that fail — the ticker simply vanishes from the result, so `price_map` has no key
     for it → `.get` returns the `0` default.
   - Alpha Vantage's free tier returns **HTTP 200 with a rate-limit notice** when
     throttled. `raise_for_status()` passes, `resp.json()` has no `Global Quote`, and
     `float(raw.get("05. price", 0))` → `0.0`. A "successful" response yields a $0 price.

Under load (a ~100-name candidate universe hammering the free tier) many tickers hit one
of these paths every cycle, so snapshots routinely zeroed out real holdings.

**Why tests never caught it:** every snapshot test mocked `get_quotes()` returning
*complete* coverage. A mock that always succeeds cannot reproduce a partial-failure bug.

## Solution

Merged in `d24c98b` (PR #38). Four parts:

1. **Price from Alpaca, not Alpha Vantage.** Snapshots now use
   `technical_analysis.get_indicators()` — the same batched, crypto-aware, day-cached
   source the executor trades on, so snapshots and execution agree on price.

   ```python
   indicators = await get_indicators(sorted(all_tickers))
   for ticker, data in indicators.items():
       price = data.get("price", 0)
       if price > 0:
           price_map[ticker] = price
   ```

2. **Carry forward the last known price on an outage**, bounded so a real drawdown can't
   hide behind a stale price. Backed by a new `ticker_prices` table.

   ```python
   MAX_CARRY_FORWARD_DAYS = 7
   stale_cutoff = today - timedelta(days=MAX_CARRY_FORWARD_DAYS)
   for ticker in all_tickers - price_map.keys():
       cached = db.query(TickerPrice).filter(TickerPrice.ticker == ticker).first()
       if cached and cached.as_of >= stale_cutoff:
           price_map[ticker] = float(cached.price)   # carry forward
       else:
           logger.error("No live price for %s and no usable carry-forward", ticker)
   ```

3. **Refuse to write a snapshot the portfolio can't be fully priced for.** A gap in the
   equity curve is honest; a partial total reads as a real loss to the Phase G gate.

   ```python
   unpriced = [t for t in positions if t not in price_map]
   if unpriced:
       logger.error("Skipping snapshot for plan %d — unpriced: %s", plan.id, unpriced)
       continue
   ```

4. **Backfilled the corrupted history** — 16 `plan_snapshots` rows for portfolio 6
   rebuilt from the trade ledger valued at real Alpaca daily closes (dry-run-first script).

Covered by 4 regression tests, including one that reproduces the exact bug: a held
position whose quote is missing must value from Alpaca, never $0.

## Prevention

- **Never default a price (or any measurement) to `0`.** `.get(key, 0)` for a value that
  flows into arithmetic makes "I don't know" indistinguishable from "it's worthless."
  Propagate `None`, raise, or skip — never substitute a number for missing data. This is
  the same principle applied in the risk engine (`RiskError` on missing ATR — see
  [[PRD-002]]).
- **A 200 response is not a success.** External APIs (Alpha Vantage especially) return
  HTTP 200 with an error/throttle body. Validate the *payload shape*, not just the status
  code.
- **When one consumer patches around a data source's flaw, audit every other consumer.**
  The executor already knew `get_quotes()` returns $0 under load and patched it; snapshots
  was left behind. A shared flaw needs a shared fix, not a per-caller workaround.
- **A mock that always returns complete data cannot catch a partial-failure bug.** Tests
  for a degradation path must simulate the degradation (dropped tickers, empty payloads),
  not the happy path. See [[DOC-010]] (testing strategy — "ugly cases").
- **Open risk (still open):** other call sites of `get_quotes()` have not been audited for
  the same `.get(..., 0)` pattern. Tracked as RISK-002 in [[DOC-017]].

## Related

- [[DOC-017]] — risks register (RISK-002: missing data → number, still open as a class)
- [[DOC-018]] — experiment log (EXP-001: this corruption invalidated Test 5's measured run)
- [[PRD-002]] — risk engine applies the same "missing data never becomes a value" rule
- `crypto-tickers-in-stock-client-prompt.md` — sibling "silent wrong price" logic error
- PR #38 · commit `d24c98b`
