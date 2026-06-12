---
name: universe-widening-broke-shared-infra-scale-assumptions
description: Widening the maximize_returns universe from 9 to ~100 tickers (and adding a ~500-name screener) silently broke two pieces of shared infra that were written for a handful of symbols — fetch_and_cache_bars did one Alpaca request per ticker (500 sequential calls), and get_quotes fanned ~100 parallel Alpha Vantage calls per cycle that burned the free-tier daily quota shared with the get_news call, risking Claude trading on empty news. No errors; tests passed; only a multi-agent review caught it.
type: performance-issue
severity: high
component:
  - backend/app/backtest/data.py
  - backend/app/plans/executor.py
  - backend/app/market_data.py
  - backend/app/claude_brain.py
tags: [scale, rate-limiting, alpaca, alpha-vantage, shared-dependency, n-plus-one, silent-failure, universe, screener, code-review]
date: 2026-05-21
status: resolved
---

# Widening the Universe Silently Broke Two Scale Assumptions in Shared Infra

## Problem

Two changes landed the same week:
1. `maximize_returns` universe widened from 9 mega-cap names to ~100 (`MAXIMIZE_RETURNS_UNIVERSE`).
2. A new screener that scans ~500 S&P 500 names daily.

Both reused existing infra — `backtest.data.fetch_and_cache_bars` for OHLCV and `market_data.get_quotes` for live quotes — that had been written when the ticker set was a handful of names. At the new scale, two latent assumptions broke:

- **`fetch_and_cache_bars` made one Alpaca request per ticker.** The screener fed it ~500 names → ~500 sequential network round-trips per cold run (~3–5 min, right at Alpaca's rate ceiling). A manual `/screener/refresh` during market hours ran the same serial scan.
- **`get_quotes` fanned out one parallel Alpha Vantage call per ticker.** The widened ~100-name universe meant ~100 simultaneous GLOBAL_QUOTE calls **every trading cycle** against a free tier of ~5/min (25/day). ~95 were throttled to `price=0` and **thrown away** (prices are already backfilled from Alpaca indicators) — but they burned the daily quota, and `get_news` **shares the same API key**. So the wasteful quote storm could exhaust the quota and silently leave Claude trading on **empty news**.

Neither raised an error. All 477 tests passed. Trades kept executing (prices survived via the Alpaca backfill). The damage was invisible at the unit-test layer.

## How It Was Discovered

A multi-agent `/ce:review` of the merged session diff (`b7db5ff..HEAD`), **after** the work shipped per-PR. Two independent reviewers (a Python reviewer and a performance reviewer) flagged the sequential fetch as the single highest-leverage issue; the performance reviewer separately traced the `get_quotes` fan-out to shared-key quota exhaustion starving `get_news`. Tests didn't catch either because the data layer is mocked in the screener/executor tests — the scale behavior only exists against the real APIs.

## Root Cause

**One trigger, two mechanisms.** Reusing shared infra is correct (re-implementing OHLCV fetch/quotes would be worse duplication). The miss was **not re-auditing the scale assumptions of that infra when the input that feeds it grew ~10–50×.**

- `fetch_and_cache_bars` looped `for ticker in tickers: client.get_stock_bars(symbol_or_symbols=[ticker])` — a per-item network call (an N+1 against an external API). Fine for a backtest's handful of tickers; pathological at 500.
- `get_quotes` did `asyncio.gather(*(get_quote(t) for t in tickers))` — unbounded fan-out against a rate-limited, **shared-key** dependency. The blast radius wasn't the quotes themselves (discarded + backfilled) but the *collateral* starvation of the news call sharing the key.

## The Fix

**1. Batch the fetch** (`backtest/data.py`). Alpaca's `StockBarsRequest` accepts a list of symbols; chunk the uncached tickers (~100/request) and split the multi-index response per ticker. ~500 calls → ~5. Template already existed 30 lines away in `technical_analysis._fetch_daily_bars`.

```python
for i in range(0, len(to_fetch), _FETCH_CHUNK):       # _FETCH_CHUNK = 100
    chunk = to_fetch[i:i + _FETCH_CHUNK]
    request = StockBarsRequest(symbol_or_symbols=chunk, timeframe=TimeFrame.Day, start=start, end=end)
    bars_df = (await asyncio.to_thread(client.get_stock_bars, request)).df
    multi = isinstance(bars_df.index, pd.MultiIndex)
    for ticker in chunk:
        tdf = bars_df.loc[ticker] if multi else bars_df
        # ...cache rows not already present...
```

**2. Scope the quote fan-out to held positions** (`plans/executor.py`). Don't quote the full universe via Alpha Vantage — candidate prices already come from the Alpaca indicator batch + price-patch. Quote only what's actually held (a handful), protecting the shared key for `get_news`.

```python
position_tickers = {held account + virtual positions}      # a handful
all_tickers      = position_tickers | watchlist | overrides # full universe
quote_syms = sorted(position_tickers)
quotes_task     = market_data.get_quotes(quote_syms)        # held only — not the ~100 universe
indicators_task = get_indicators(held_tickers)              # one batched Alpaca call covers the universe
```

Verified: batched fetch smoke-tested end-to-end against live Alpaca (6 tickers, correct per-ticker split, cache-hit on rerun); a regression test asserts quotes are not fanned over the universe (`tests/plans/test_fetch_market_data.py::test_quotes_not_fanned_over_the_universe`).

## Prevention

- **When you scale a config input (a universe, a batch size, a fan-out width), re-audit every shared component that consumes it.** The bug wasn't in the new code — it was in old code whose small-N assumption the new code violated. Grep the call graph of the changed input.
- **Per-item calls are an N+1 — batch them — and the network call is rarely the *only* one.** Batch against the API's bulk endpoint (here, copy `technical_analysis._fetch_daily_bars`). But note: this exact function had **two** N+1s stacked. The first fix (PR #26) batched the *network* fetch (~500 Alpaca calls → ~5); a follow-up `/ce:review` then found the *coverage check* still did one **DB** `SELECT` per ticker (~500 pooler round-trips), fixed in PR #27 with a single `WHERE ticker IN (...)` query. When you kill one N+1, scan the same function for the next — they nest.
- **Unbounded `asyncio.gather` over a rate-limited or shared-key dependency is a footgun.** Cap concurrency, or — better — don't make the calls at all if the data is available from a cheaper source (here, Alpaca indicators already provided prices). Watch especially for *collateral* starvation: a wasteful fan-out on a shared key can kill a different, load-bearing call.
- **Mocked-boundary tests won't catch scale/rate problems.** Add at least one smoke test against the real API for shared data-fetch infra, and a guard test that pins the intended call scope (e.g. "quotes cover held only"). *Done:* `tests/test_backtest_data.py` now exercises the real SQLite cache with a mocked Alpaca boundary, pinning gap-fill (cached ticker skipped), the cache-hit no-op (Alpaca never called), and the batch shape (uncached tickers fetched in one request) — and `tests/plans/test_fetch_market_data.py::test_quotes_not_fanned_over_the_universe` pins the quote scope.
- **Run a review on net-new code even when it shipped per-PR with green tests.** Both issues passed CI; only `/ce:review` surfaced them.

## Related

- `docs/solutions/integration-issues/strategy-params-tickers-ignored-in-claude-mode.md` — the other half of the universe-widening work; same theme of a change interacting badly with infra that wasn't updated for it.
- `docs/solutions/logic-errors/crypto-tickers-in-stock-client-prompt.md` — another silent data-pipeline failure in the same `claude_brain.py` / market-data area.
- Shipped in PR #26 (review fixes), following the universe widening (PR #20) and screener (PR #22). PR #27 fixed the recursive coverage-check N+1 found by re-review and added the guard tests above.
