---
id: DOC-006
type: todos
status: active
phase: null
owner: james
tags: [foundations]
links: [DOC-005]
updated: 2026-07-22
---

# To-dos (micro)

**What this is, in plain English:** the short list. Small, immediately actionable, and
attached to something bigger. If you cannot say which roadmap item a to-do serves, that
is a signal the work may be drift rather than progress.

Each gets a stable `TD-###` id and links to the roadmap item (`RM-###`) and PRD it
serves.

> There is a separate admin to-do tool at `/todos` backed by `backend/data/todo-tasks.json`.
> That one is a scratch queue for operational tasks. This file is the durable list that
> ties work to goals. If a task matters in a month, it belongs here.

## The "done" convention

Same as the roadmap: nothing moves, nothing gets archived. Finished to-dos stay in the
table with `status: done` and drop out of the default view via a saved filter. The
record of what was done and when is worth more than a short list.

## Open

| id | To-do | Serves | Status | Notes |
|---|---|---|---|---|
| TD-001 | Bracket-order support in broker layer (stop_price leg) | RM-001 | draft | `brokers/base.py`, `brokers/alpaca.py`; whole-share only |
| TD-002 | Wire risk sizing + ATR stop into executor entry path | RM-001 | draft | **Cap qty by cash/headroom** (review finding, PRD-002) |
| TD-003 | Add risk_pct / atr_multiple to Portfolio; stop_price to Trade | RM-001 | draft | model fields + create_all registration |
| TD-004 | Create Test 6 portfolio ($10k, risk engine active) | RM-002 | draft | deactivate + preserve Test 5 |
| TD-005 | Trailing-stop ratchet on the daily cycle | RM-001 | draft | never lowers a stop |
| TD-006 | Portfolio heat cap + per-sector cap | RM-001 | draft | ≤5% open risk; ≤2 per industry |
| TD-007 | Delete quarter-Kelly sizing; remove prompt stop sentence | RM-001 | draft | superseded by risk engine |
| TD-008 | Forex settings toggle (hide nav group, default off) | RM-001 | draft | the original request that started this |

## Done

<!-- Kept deliberately. This is the record of velocity — how long things actually took
     versus how long they were expected to take. -->

| id | To-do | Serves | Completed | Notes |
|---|---|---|---|---|
| TODO | | | | |
