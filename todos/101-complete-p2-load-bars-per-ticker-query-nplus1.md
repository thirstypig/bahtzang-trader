---
status: complete
priority: p2
issue_id: "101"
tags: [code-review, backend, performance, database]
dependencies: []
---

# load_bars Is the Third Nested N+1 on the Same OHLCV Path

## Problem Statement

PR #26 batched the network fetch (~500 Alpaca calls → ~5). PR #27 collapsed the coverage check (~500 SELECTs → 1). But `load_bars` — called immediately after `fetch_and_cache_bars` by every caller, with the same ticker list — still issues **one query per ticker**: ~500 sequential round-trips through the Supabase pooler on the daily 7:30 AM screener path.

This is exactly the documented lesson from `docs/solutions/performance-issues/universe-widening-broke-shared-infra-scale-assumptions.md`: "When you kill one N+1, scan the same function for the next — they nest." It nested a third time, one function over.

## Findings

- `backend/app/backtest/data.py:128-137` — `for ticker in tickers:` → one `db.query(OHLCVCache).filter(ticker == ...)` each.
- Callers that pay it at scale: `backend/app/screener/engine.py:187-188` (~500 tickers daily), `backend/app/plans/executor.py:139-140`, `backend/app/backtest/engine.py:47-50`.
- At 5–20ms per pooler round trip: ~2.5–10s of serialized DB latency per screener run, re-reading rows the coverage check just touched.
- Index `ix_ohlcv_ticker_date (ticker, bar_date)` exists, so the batched variant is index-friendly.

## Proposed Solutions

1. **(Recommended)** Same pattern as PR #27's fix: one query `WHERE ticker IN (...) AND bar_date BETWEEN ... ORDER BY ticker, bar_date`, split into per-ticker DataFrames in Python (groupby on ticker). Effort: Small. Risk: Low — pin with a test mirroring `tests/test_backtest_data.py`.
2. `pd.read_sql` + `df.groupby(level="ticker")` — same query, pandas does the splitting. Effort: Small. Risk: Low, slightly more magic.

## Acceptance Criteria

- [ ] `load_bars` issues one query regardless of ticker count
- [ ] Guard test pins the single-query behavior (count queries or mock the session)
- [ ] Existing backtest/screener/executor tests still green

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-06-11 | Created from performance-oracle finding during /ce:review of PR #27 | Third stacked N+1 in the same pipeline — the solution doc's "they nest" warning keeps paying out |
| 2026-06-11 | Fixed: load_bars now one grouped query (ticker IN + ORDER BY ticker, bar_date), split per-ticker in Python. Guard test counts SELECTs via before_cursor_execute listener. | Shipped same-day in feat/exit-cycle-cost-basis-and-window |
