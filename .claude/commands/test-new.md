Write tests for a newly added or modified feature, then execute them and document.

The argument `$ARGUMENTS` is the feature name or area (e.g. `plans`, `executor`, `earnings`, `PlanPositions`).

## Phase 1 — Understand what changed

1. Run `git diff main...HEAD --stat` and `git log main..HEAD --oneline` to see what this session touched.
2. For the target feature, read the primary source file(s) and list:
   - Pure functions (easy unit tests)
   - React components with local state (unit tests via Testing Library)
   - FastAPI endpoints (integration tests via TestClient with SQLite)
   - Async functions calling external APIs (unit tests with mocked broker/Claude)
   - User-facing flows (E2E candidates — only if they'd cost real money when broken)
3. Read the admin `/testing` page source (`frontend/src/app/testing/page.tsx`) to see what coverage already exists.

## Phase 2 — Write tests (pyramid order)

For each new piece of behavior, add in this order. Stop after each tier unless the feature truly warrants the next.

1. **Unit tests**
   - Backend: place in `backend/tests/<module>/test_<name>.py`. Use `db_session` fixture from conftest. Mock external deps (broker, Claude, market_data) with `unittest.mock.patch` + `AsyncMock`.
   - Frontend: co-locate at `src/<dir>/<name>.test.ts(x)`. Mock fetch via `vi.mock`. Mock Recharts if testing chart components.
   - Name tests after the behavior, not the function: `"blocks sell when plan owns zero shares"` not `"test_sell_validation"`.
   - Cover: the happy path, 1–2 edge cases, and the bug that motivated the feature if applicable.

2. **Integration test** — only if the feature crosses modules. Backend: use the `client` fixture from conftest (FastAPI TestClient + SQLite). Frontend: not applicable until E2E.

3. **E2E test** — only if:
   - The flow costs real money when broken (trade execution, budget validation), OR
   - The flow regressed silently in the past and unit tests didn't catch it.

## Phase 3 — Execute

Run in this order, stopping on the first failure:

1. `cd frontend && npx tsc --noEmit` (typecheck)
2. `cd backend && source venv/bin/activate && python -m pytest tests/ -v --tb=short` (backend)
3. `cd frontend && npx vitest run` (frontend)

## Phase 4 — Document

1. Update `frontend/src/app/testing/page.tsx`:
   - Add the new test file(s) to the relevant suite in the `TESTS` object.
   - Update the test counts.
2. If the new tests expose a previously-silent bug, note it in the test file as a comment.

## Phase 5 — Report

Respond in this exact shape:

```
Feature: $ARGUMENTS
Unit tests added: N  (file paths)
Integration tests: N (file paths, or "not needed")
E2E tests: N         (file paths, or "not needed — reason")
Typecheck: green
Full suite: X passing (was Y before)
Testing page: updated (lines changed)
```

## Phase 6 — Decide if commit-worthy

If tests are green and the feature is code-complete, say so and ask whether to commit. If something is half-baked, flag it — don't silently commit partial work.

## Guardrails

- **Don't write tests the feature will pass by definition.** A test like "calling foo() returns what foo() returns" catches nothing. Tests must encode behavior the *caller* depends on.
- **Don't mock what you're testing.** Mock the boundary (DB, HTTP, broker, Claude), not the unit under test.
- **If you can't name a concrete past or plausible regression the test prevents, consider not writing it.** Every test is code to maintain.
- **Flaky test = broken test.** Fix the root cause — don't add retries.
