---
status: pending
priority: p1
issue_id: "024"
tags: [code-review, logic-bug, guardrails, critical]
dependencies: []
---

# max_positions Query Counts All-Time Buys, Never Subtracts Sells

## Problem Statement

The `max_positions` guardrail check counts every distinct ticker that has EVER had a buy trade executed. It never subtracts sells. Over time, this counter only grows, eventually blocking all new buys even when the portfolio is empty. The bot will silently stop trading within weeks.

**Found by:** Python reviewer (P1), Performance oracle (HIGH), Architecture strategist (MEDIUM)

## Findings

- `backend/app/guardrails.py:204-212` — Query counts `DISTINCT(Trade.ticker)` where `action == "buy"` and `executed == True`
- Buy AAPL, sell AAPL = still counted as 1 position
- After trading ~10 unique tickers (moderate profile), bot permanently locked out of buying
- This is a ticking time bomb that gets worse as trade history grows

## Proposed Solutions

### Option A: Query broker for actual positions (Recommended)
- Pass broker positions count into `check_guardrails()` from `_execute_cycle()`
- Positions are already fetched via `broker.get_positions()` at the start of each cycle
- **Pros:** Ground truth from broker, no stale data
- **Cons:** Requires signature change to `check_guardrails()`
- **Effort:** Small
- **Risk:** Low

### Option B: Compute net positions from trade history
- Count buys minus sells per ticker, only count tickers with net positive shares
- **Pros:** No external dependency
- **Cons:** Still not ground truth (partial fills, manual trades not captured)
- **Effort:** Small
- **Risk:** Medium

## Acceptance Criteria

- [ ] Selling a position reduces the position count
- [ ] Bot can buy new tickers after selling old ones
- [ ] Position count reflects actual open positions, not all-time history

## Work Log

| Date | Action | Result |
|------|--------|--------|
| 2026-04-10 | Code review found issue | 3 agents flagged independently |
