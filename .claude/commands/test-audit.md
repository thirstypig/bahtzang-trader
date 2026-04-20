Audit the test infrastructure and recommend the single highest-leverage next investment.

This is a **decision-support prompt**, not an install prompt. It produces a status table and a recommendation. The user decides whether to install anything.

## Scan

Detect the presence of each item by running specific checks. Do not speculate — if a check is ambiguous, mark it "unclear" and explain why in one line.

1. **Pre-commit hook**
   - `cat .claude/settings.json 2>/dev/null` — look for a hook matching `git commit`.
   - `ls .husky/pre-commit 2>/dev/null` — Husky-style git hook.
   - `ls .git/hooks/pre-commit 2>/dev/null` — native git hook (not just `.sample`).
   - Present if any of the above run tsc or tests.

2. **Contract testing (shared types client ↔ server)**
   - Check if TypeScript types in `frontend/src/lib/types.ts` match Python Pydantic models in `backend/app/plans/routes.py` and `backend/app/plans/models.py`.
   - Count how many API endpoints have matching request/response types on both sides. 0 = absent. Partial = some. All = present.

3. **Visual regression**
   - `grep -r "toHaveScreenshot\|toMatchSnapshot" frontend/src` — snapshot assertions.
   - `ls frontend/e2e/__screenshots__ 2>/dev/null`.

4. **Mutation testing**
   - `grep -l "stryker\|mutant" frontend/package.json backend/requirements.txt` or `ls stryker.conf.* mutmut.ini 2>/dev/null`.

5. **CI pipeline**
   - `ls .github/workflows/*.yml 2>/dev/null`. Read the first one; confirm it runs tests.
   - Check Railway deployment config for test steps.

6. **Flaky test tracking**
   - `grep -r "flaky\|\.only\|\.skip\|xfail" backend/tests/ frontend/src/ 2>/dev/null` — informal signals.

7. **Test factories / fixtures**
   - Backend: check `backend/tests/conftest.py` for `make_plan`, `make_trade` helpers.
   - Frontend: check for shared mock/factory utilities.

8. **Coverage tracking**
   - `grep -l "pytest-cov\|coverage" backend/requirements.txt` and `grep -l "coverage" frontend/vitest.config.ts frontend/package.json`.

## Report

Output exactly this shape:

```
Test Infrastructure Audit:

✓ Pre-commit hook     — <one-line evidence>
✗ Contract testing    — <one-line evidence>
✓ Visual regression   — <one-line evidence>
...

Recommended next: <item>.
  Why:      <one-sentence impact — cite a real bug or gap this would prevent>.
  Cost:     <estimate — "1 session" / "10 min config" / "1 week incremental">.
  Trade-off: <what it complicates or what you lose>.
  Next step: <single sentence — what the user would say to start it>.
```

## Ranking rules (how to pick "Recommended next")

Prefer items that:

1. **Prevent a bug class we've actually shipped.** A contract testing recommendation that cites the CycleResult quantity int/float mismatch (todo 094) beats an abstract "coverage is good" pitch.
2. **Have the highest bug-prevention-per-hour ratio.** Pre-commit hook: 10 min to install, prevents most "forgot to run tests" commits — excellent ratio. Visual regression: 2 hours to wire + ongoing screenshot maintenance — only recommend when CSS drift has bitten you.
3. **Unblock later items.** CI pipeline should come before mutation testing and visual regression, because those are most valuable running on every PR, not just locally.

When the user hasn't installed anything, the typical order is:
**pre-commit → CI → contract testing → test factories → coverage → visual regression → mutation testing → flaky tracking**.

## Guardrails

- **Don't install anything.** This prompt only reads and recommends. If the user says "do it" after seeing the report, run the appropriate install flow as a separate step.
- **Don't over-recommend.** One item at a time. A list of seven is a to-do, not a decision.
- **Cite concrete evidence.** "No shared schemas" is weak. "0 shared type contracts; the CycleResult int→float bug (094) would have been caught by a shared schema" is strong.
- **If everything is installed:** congratulate briefly and recommend running the existing tooling (mutation testing sweep, coverage report) rather than inventing new items.
