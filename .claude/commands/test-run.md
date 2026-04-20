Run the full test dance (typecheck → backend → frontend) and report cleanly.

## Steps

Run these in sequence. Stop at the first failure — don't mask errors by continuing.

1. **Typecheck:**
   - `cd frontend && npx tsc --noEmit`

2. **Backend tests (pytest):**
   - `cd backend && source venv/bin/activate && python -m pytest tests/ -v --tb=short`
   - Report: `<passed> passed, <failed> failed` with timing

3. **Frontend tests (Vitest):**
   - `cd frontend && npx vitest run`
   - Report: `<passed> passed, <failed> failed` with timing

4. **E2E (optional — only if `$ARGUMENTS` contains `e2e`):**
   - Verify dev servers: `curl -s -o /dev/null -w "%{http_code}" http://localhost:3060` and `http://localhost:4060/health`. Both must be 200.
   - If either is down: tell the user which one, don't try to start it yourself.
   - If both up: run E2E tests. Report time per spec + total.

## Report format

Keep it terse. Aim for this shape:

```
✓ tsc frontend    (Xs)
✓ N backend       (Xs)
✓ N frontend      (Xs)
Total: N tests green
```

On failure:
```
✗ <where> — <file:line>: <assertion>
<next steps — one sentence>
```

## Arguments

- `/test-run` — typecheck + backend + frontend (no E2E). Fast — use before commits.
- `/test-run e2e` — full dance including E2E. Use before push.
- `/test-run <feature>` — typecheck + only tests matching `<feature>`. Use during iteration.

## Guardrails

- **Don't skip on "known flakes."** Flakes are bugs — report them honestly.
- **Don't retry automatically.** If the first run fails, show the failure. Let the user decide whether to retry.
- **Never suppress output to make things look clean.** Tail + summarize is fine; silently swallowing errors is not.
