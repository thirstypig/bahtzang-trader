---
title: Feature Module Isolation Pattern for FastAPI + Next.js Monorepo
date: 2026-04-13
category: integration-issues
tags:
  - architecture
  - feature-modules
  - fastapi
  - monorepo
  - separation-of-concerns
  - scalability
component: Backend architecture (FastAPI application structure)
symptom: Prevents architectural tangling when adding multiple complex features to shared codebase
root_cause: Without isolated feature modules, new business logic couples with core app, creating circular dependencies and making features difficult to test, maintain, and remove independently
severity: medium
time_to_fix: Pattern established during Phase F planning, applied to both backtesting and earnings features
verified: true
---

# Feature Module Isolation Pattern

## Problem

When adding two major features simultaneously (backtesting framework + earnings calendar) to a FastAPI + Next.js monorepo, the codebase risked becoming scattered and unmaintainable:

- Feature-specific models would pollute the root `models.py`
- Routes would be registered ad-hoc without clear structure
- Integration touchpoints would be unpredictable and implicit
- Testing would be difficult with tight coupling to core modules
- Future features would lack a clear pattern to follow

## Root Cause

Adding features to a monorepo without explicit module isolation leads to:

- Implicit dependencies on shared infrastructure
- Difficult to understand what a feature "needs" to run
- Risk of breaking existing code when adding feature integrations
- No clear contract between features and core platform

## Solution: Self-Contained Python Packages

Each feature is a self-contained Python package under `backend/app/` with a clear, minimal interface for integration.

### Directory Structure

```
backend/app/
  backtest/                    # Feature module
    __init__.py
    models.py                  # BacktestConfig, BacktestResult, OHLCVCache
    data.py                    # OHLCV fetch + PostgreSQL cache
    engine.py                  # Day-by-day simulation
    strategies.py              # Pluggable strategy interface + built-ins
    routes.py                  # API endpoints (CRUD + run)
  earnings/                    # Feature module
    __init__.py
    models.py                  # EarningsEvent
    client.py                  # Finnhub API + DB cache
    routes.py                  # API endpoints

frontend/src/app/
  backtest/page.tsx            # Config form, results, equity curve chart
  earnings/page.tsx            # Calendar view with color-coded proximity
```

### Integration Touchpoints (The ONLY Changes to Existing Code)

| File | What Changes | Lines Added |
|------|-------------|-------------|
| `models.py` | Import feature models for `create_all()` | 2 |
| `main.py` | `include_router()` calls | 2 |
| `config.py` | Feature-specific env var | 1 |
| `scheduler.py` | Cron job for earnings refresh | ~15 |
| `trade_executor.py` | Pass earnings data to Claude + position cap | ~10 |
| `claude_brain.py` | New parameter + prompt addition | ~5 |
| `position_sizing.py` | Optional parameter + graduated reduction | ~5 |
| `Navbar.tsx` | 2 new nav links | 2 |

### Key Code Patterns

**Model registration** — import in root `models.py` so `create_all()` picks up tables:

```python
# app/models.py
from app.backtest.models import BacktestConfig, BacktestResult, OHLCVCache  # noqa: F401
from app.earnings.models import EarningsEvent  # noqa: F401
```

**Router registration** — one line per feature in `main.py`:

```python
from app.backtest.routes import router as backtest_router
from app.earnings.routes import router as earnings_router
app.include_router(backtest_router)
app.include_router(earnings_router)
```

**Feature routes** — standard FastAPI pattern with auth:

```python
router = APIRouter(prefix="/backtest", tags=["backtest"])

@router.post("/")
async def create_and_run(
    body: BacktestCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    ...
```

**Pipeline integration** — optional parameters with graceful defaults:

```python
# position_sizing.py — earnings_days is optional, None = no reduction
def kelly_position_size(..., earnings_days: int | None = None) -> float:
    if earnings_days is not None and earnings_days <= 1:
        fraction *= 0.50  # Halve position near earnings
```

## Why This Works

1. **Deletable** — remove the entire `backtest/` directory + 2 import lines and the feature is gone
2. **Testable** — each module can be tested in isolation (mock database, broker, API client)
3. **Extensible** — adding a third feature follows the same formula
4. **Readable** — new contributors know exactly where a feature lives

## When to Use This Pattern

**Use it when:**
- Feature has 3+ files with distinct concerns (models, routes, logic)
- Feature needs its own database tables
- Feature has separate API endpoints with a clear URL prefix
- Business logic is self-contained

**Don't use it when:**
- Simple CRUD endpoint for core data (keep in `routes/`)
- Single utility function used everywhere (keep in existing files)
- Logic tightly couples with existing features (e.g., compliance checks)

## Checklist for New Feature Modules

- [ ] Create `backend/app/{feature}/` with `__init__.py`
- [ ] Define models in `{feature}/models.py` inheriting from `Base`
- [ ] Import models in root `models.py` for table creation
- [ ] Create `{feature}/routes.py` with `APIRouter(prefix="/{feature}")`
- [ ] Register router in `main.py`
- [ ] All routes use `Depends(require_auth)` and `Depends(get_db)`
- [ ] Add config vars to `config.py` with defaults (never required)
- [ ] Create frontend page in `app/{feature}/page.tsx`
- [ ] Add types to `types.ts` and API functions to `api.ts`
- [ ] Add nav link to `Navbar.tsx`

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Importing from sibling features (backtest/ importing from earnings/) | Extract shared logic to `app/` utilities (e.g., `analytics.py`) |
| Defining feature models in root `models.py` | Keep models in `{feature}/models.py`, only import for registration |
| Creating global instances of external clients at module scope | Use dependency injection or lazy initialization |
| Feature tests requiring the entire app to run | Mock database and external APIs, test in isolation |
| Background tasks receiving DB sessions as parameters | Create `SessionLocal()` inside the task; sessions don't survive across threads |

## Applied Examples

### Backtest Module (Phase F)
- 6 files, 845 lines
- 3 database tables (backtest_configs, backtest_results, ohlcv_cache)
- Background execution via FastAPI BackgroundTasks
- Reuses `analytics.compute_metrics()` and `technical_analysis._compute_indicators()`

### Earnings Module (Phase F)
- 4 files, 241 lines
- 1 database table (earnings_events)
- 1 Finnhub API call/day, aggressive DB caching
- Graduated position reduction: 50% at 0-1 days, 70% at 2 days before earnings

## Cross-References

- PR #10: `feat/phase-f-backtest-earnings` — initial implementation
- `CLAUDE.md`: Feature Module Isolation convention documented
- `frontend/src/data/roadmap.ts`: Phase F items marked in-progress
