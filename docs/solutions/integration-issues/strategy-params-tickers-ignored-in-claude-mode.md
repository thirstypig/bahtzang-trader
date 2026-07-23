---
id: DOC-042
type: solution
status: active
phase: null
owner: james
tags: [strategies, trading-pipeline]
links: []
updated: 2026-05-21
description: A portfolio's strategy_params["tickers"] override was honored by the rules-strategy execution path but silently ignored by the claude_decides path. Setting the param on a Claude-mode portfolio had no effect — the extra tickers never reached the market-data fetch, so Claude never saw them. No error; the config was simply dead.
severity: medium
legacy_type: integration-issue
---

# strategy_params["tickers"] Honored in Rules Mode, Silently Ignored in Claude Mode

## Problem

Each portfolio can carry a `strategy_params` JSON blob. For rule-based strategies it holds the strategy's parameters (SMA windows, an explicit `tickers` list, etc.). The intent was that `strategy_params["tickers"]` could also widen the candidate universe for a `claude_decides` portfolio — hand-add symbols for Claude to consider.

It didn't work. Setting `strategy_params["tickers"] = ["FOO"]` on a `claude_decides` portfolio had **zero effect**: Claude never received `FOO` in its market data, never quoted it, never traded it. No exception, no warning, no log line — the value was just inert config.

This surfaced while scoping how to widen the active Test 4 portfolio's universe. The initial (wrong) recommendation was "just set the `tickers` param — no code change needed." Tracing the code disproved it.

## How It Was Discovered

Test 4 runs in `claude_decides` mode. To confirm whether the param route would work, both executor paths were read end to end:

- **Rules path** (`_get_strategy_decisions` in `executor.py`) builds its universe and *does* read the param:
  ```python
  tickers: set[str] = set(virtual_positions.keys())
  tickers.update(GOAL_WATCHLIST.get(plan.trading_goal, []))
  if isinstance(params.get("tickers"), list):
      tickers.update(params["tickers"])   # ← honored here
  ```

- **Claude path** (`fetch_market_data` in `executor.py`) builds a *separate* universe and never touches `strategy_params`:
  ```python
  all_tickers = {p.get("instrument", {}).get("symbol", "") for p in positions}
  for pid in plan_ids:
      all_tickers.update(compute_virtual_positions(db, pid).keys())
  if plans:
      for plan in plans:
          all_tickers.update(GOAL_WATCHLIST.get(plan.trading_goal, []))
  # strategy_params["tickers"] never read → claude_decides ignores it
  ```

Same column, two independent consumers, two different behaviors.

## Root Cause

The candidate universe is assembled in **two places** because the two decision modes have separate data paths:

- `rules_decide` / `rules_with_claude_oversight` → `_get_strategy_decisions` fetches its own bars and reads `strategy_params`.
- `claude_decides` → `fetch_market_data` assembles quotes/technicals/news for the Claude prompt from `account positions + virtual positions + GOAL_WATCHLIST`.

When the `tickers` param was added, only the rules path was wired to read it. The Claude path was never updated, so the override was a no-op there. Because the field is optional, a missing effect looks identical to "user didn't set it" — nothing fails, making it a **silent** divergence.

This is the same shape as a prior bug in this repo where one pipeline diverged from another's assumptions (see Related), and it's especially easy to hit here because the system has **three decision modes** that don't share a single universe-building function.

## The Fix

Union `strategy_params["tickers"]` into the Claude path's universe in `fetch_market_data`, with the same `isinstance` guard the rules path uses (defensive against a malformed non-list value being iterated character-by-character):

```python
if plans:
    for plan in plans:
        all_tickers.update(GOAL_WATCHLIST.get(plan.trading_goal, []))
        # Per-portfolio universe override (claude_decides path). Also the slot a
        # daily screener writes its top candidates into. Previously only the
        # rules-strategy path honored it, so Claude-mode portfolios ignored it.
        extra = (plan.strategy_params or {}).get("tickers")
        if isinstance(extra, list):
            all_tickers.update(t for t in extra if isinstance(t, str) and t)
all_tickers.discard("")
```

With this, a `claude_decides` portfolio's `tickers` override flows into the quotes/technicals fetch and reaches the Claude prompt. This same slot is now the integration point a daily screener writes its top-ranked candidates into, and the Decision Engine UI exposes it as an "Additional Tickers" field.

## Prevention

- **Test every execution path, not just one.** `tests/plans/test_fetch_market_data.py` asserts the override reaches the Claude-path universe **and** that a malformed (non-list) param is ignored rather than char-splatted:
  ```python
  plan = _make_plan(db_session, {"tickers": ["ZZZZ"]})
  universe = await _universe_passed_to_fetch(db_session, plan)
  assert "ZZZZ" in universe and "AAPL" in universe   # override + watchlist both present
  ```
- **Treat "config that silently does nothing" as a bug class.** When a feature reads a per-portfolio field, grep for *every* place the relevant artifact is built. In this codebase the universe is built in two functions; decision-mode features must touch both (or be refactored to share one builder).
- **Prefer a single source of truth.** The deeper fix is a shared `build_universe(plan)` helper used by both paths so a new input can't be wired into one and forgotten in the other. Deferred (the two paths fetch different shapes of data), but the duplication is the root hazard.
- **Validate optional config at the boundary.** The `isinstance(extra, list)` guard prevents a string param (`"AAPL,MSFT"`) from being iterated into single characters — a failure that would otherwise be silent and corrupt the universe.

## Related

- `docs/solutions/logic-errors/crypto-tickers-in-stock-client-prompt.md` — same file family (`GOAL_WATCHLIST` / `claude_brain.py`), also a silent data-pipeline mismatch.
- `docs/solutions/integration-issues/feature-module-isolation-pattern.md` — module-boundary conventions; the executor's reuse of `backtest.data` is the relevant precedent.
- Shipped alongside the universe widening (PR #20) and the screener (PR #22), which depend on this slot being honored in Claude mode.
