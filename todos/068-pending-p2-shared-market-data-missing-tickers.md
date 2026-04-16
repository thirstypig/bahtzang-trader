---
status: pending
priority: p2
issue_id: "068"
tags: [code-review, correctness, plans, performance]
dependencies: []
---

# Shared market data fetch misses per-plan virtual positions

## Problem Statement
`run_all_plans` fetches market data based on `held_tickers` which is the GLOBAL Alpaca position list. If Plan A virtually holds AAPL (bought via a prior plan cycle) but the Alpaca position was assigned to Plan B, AAPL might not be in `held_tickers`. Similarly, if a plan wants to BUY a ticker not yet held, no quotes/indicators are fetched for it — Claude decides blind.

## Findings
- `backend/app/plans/executor.py:272` — `held_tickers = [p.get('instrument', ...).get('symbol', '') for p in positions]`
- Plans with virtual positions not reflected in Alpaca account won't get quotes

## Proposed Solution
Union held_tickers with all plans' virtual position tickers AND a watchlist:
```python
all_tickers = set(held_tickers)
for plan in active_plans:
    all_tickers.update(compute_virtual_positions(db, plan.id).keys())
# Optionally add a watchlist from plan goals (e.g., SCHD for steady_income)
quotes = await market_data.get_quotes(list(all_tickers))
```

## Acceptance Criteria
- [ ] Each plan's virtual positions get live quotes
- [ ] Plans can consider buy candidates beyond current holdings
