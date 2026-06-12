---
status: pending
priority: p3
issue_id: "102"
tags: [code-review, backend, quality, testing]
dependencies: []
---

# Coverage-Check Polish Batch: Edge Guard, Type Hints, Test Mock Contract, IPO Re-Fetch

## Problem Statement

Five small, non-blocking items from the PR #27 review. None affects reachable behavior today.

## Findings

1. **`expected == 0` edge** (`backend/app/backtest/data.py:62-65`): when `start == end`, `len(...) < 0` is always False → nothing is ever fetched, silently logged as a cache hit. Old code fetched empty-cache tickers unconditionally. Unreachable today (backtest route rejects `end <= start`; screener/executor use `today - N days`), but the guard lives in one route while the function is shared infra. Fix: early-return or validate `(end - start).days > 0` at the top of `fetch_and_cache_bars`.
2. **Type hints** (`data.py:52`): `dict[str, set]` → `defaultdict[str, set[date]]`. Same for `calls: list` → `list[list[str]]` in `backend/tests/test_backtest_data.py:38,65,73,81`.
3. **Test mock contract** (`tests/test_backtest_data.py:31-35`): the comment claims Alpaca returns a flat frame for single symbols — MODERATE confidence this is wrong for alpaca-py (`BarSet.df` may always be MultiIndex). Production handles both shapes so tests stay valid, but the flat branch may pin a shape that never occurs live. Verify against installed alpaca-py; either correct the comment or always return MultiIndex from `_df_for`.
4. **Steady-state row transfer** (`data.py:52-65`): warm-cache daily runs transfer ~145k rows (~25–40MB transient) just to conclude "all cached." Optional: two-step variant — `GROUP BY ticker, COUNT(*)` for the threshold, then date-level SELECT only for `to_fetch` tickers. NOTE: do NOT swap to GROUP BY alone — the per-date sets are load-bearing for insert dedup against the unique `(ticker, bar_date)` index (simplicity reviewer confirmed; a count-only swap is a correctness regression).
5. **Pre-existing IPO wart** (`data.py:48`): tickers with less history than the window (recent IPOs / new S&P additions) can never reach `expected * 0.9` coverage → re-fetched from Alpaca every run, forever. A `MIN(bar_date)`-aware coverage check would stop the recurring fetch volume.

## Proposed Solutions

Fix 1+2 in a single small commit (5 lines). Treat 3 as a verify-then-edit. Defer 4 and 5 unless screener cost/latency becomes visible — both are measurable-first optimizations.

- **Effort:** Small (items 1–3); Medium (4–5)
- **Risk:** Low

## Acceptance Criteria

- [ ] `fetch_and_cache_bars` guards or documents the zero-window case
- [ ] Type hints completed on the rewritten lines
- [ ] alpaca-py single-symbol df shape verified; test comment matches reality

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-06-11 | Created from kieran-python-reviewer + performance-oracle findings during /ce:review of PR #27 | |
