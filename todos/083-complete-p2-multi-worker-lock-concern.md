---
status: complete
priority: p2
issue_id: "083"
tags: [code-review, concurrency, plans, ops]
dependencies: []
---

# Per-plan lock + broker lock are in-process only — fail with multi-worker deploy

## Problem Statement
Both `_plan_locks` and `order_lock` are module-level asyncio.Lock() instances. These protect against concurrent async tasks in ONE uvicorn worker. If the backend runs with `--workers N > 1`, each worker has its own copies — the double-spend race reopens across workers.

The current Railway deploy runs a single uvicorn process, so this isn't an active issue. But it's a latent footgun — scaling to multi-worker or running the scheduler in a separate process would silently break safety.

## Findings
- `backend/app/plans/executor.py:22` — `_plan_locks: dict[int, asyncio.Lock]` is per-process
- `backend/app/brokers/alpaca.py:21` — `order_lock = asyncio.Lock()` is per-process

## Proposed Solutions

**Option A (simplest)**: Document the constraint in railway.toml and CLAUDE.md:
```toml
# backend/railway.toml
startCommand = "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-4060}"
# NOTE: Do NOT add --workers > 1. Per-plan locks and broker order_lock are
# in-process only. Multi-worker would reopen double-spend race condition.
```

**Option B (proper fix)**: Replace asyncio locks with Postgres advisory locks:
```python
db.execute(text("SELECT pg_advisory_xact_lock(:plan_id)"), {"plan_id": plan.id})
```

Advisory locks are automatically released at transaction end and work across workers/processes.

## Acceptance Criteria
- [ ] Multi-worker deployment documented OR advisory locks implemented
- [ ] Comment on `_plan_locks` and `order_lock` explaining the in-process scope
