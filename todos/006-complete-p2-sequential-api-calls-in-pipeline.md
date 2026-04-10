---
status: pending
priority: p2
issue_id: "006"
tags: [code-review, performance]
dependencies: []
---

# Sequential API Calls in Pipeline

## Problem Statement

`run_cycle` makes all external API calls sequentially. `get_quotes` fetches tickers one-by-one in a loop. Current pipeline takes ~5.7s, could be ~3.7s with parallelization. Also creates a duplicate quote fetch on line 49 after quotes were already fetched on line 32.

**Found by:** Performance oracle, Python reviewer, Pattern recognition (3 agents)

## Findings

- `backend/app/trade_executor.py`: `run_cycle` executes all external API calls in sequence rather than in parallel
- `backend/app/market_data.py`: `get_quotes` fetches tickers one-by-one in a loop instead of batching
- `backend/app/trade_executor.py` line 49: duplicate quote fetch after quotes were already fetched on line 32
- Total pipeline latency is ~5.7s when it could be ~3.7s with parallel execution

## Proposed Solutions

Use `asyncio.gather` for parallel fetches. Cache quotes to avoid the duplicate fetch. ~20 lines changed:

1. Wrap independent API calls in `asyncio.gather()` to execute them concurrently
2. Batch ticker fetches in `get_quotes` instead of looping one-by-one
3. Remove or cache the duplicate quote fetch on line 49 since data is already available from line 32

## Technical Details

**Affected files:** `backend/app/trade_executor.py`, `backend/app/market_data.py`

**Effort:** Small (~20 lines)

## Acceptance Criteria

- [ ] Independent API calls in `run_cycle` are parallelized with `asyncio.gather`
- [ ] `get_quotes` fetches multiple tickers concurrently instead of sequentially
- [ ] The duplicate quote fetch on line 49 is eliminated
- [ ] Pipeline latency is reduced from ~5.7s to ~3.7s
- [ ] Existing functionality and data accuracy are preserved
