---
status: complete
priority: p2
issue_id: "073"
tags: [code-review, typescript, plans, error-handling]
dependencies: []
---

# Frontend swallows fetch errors silently

## Problem Statement
Multiple places in the plans UI catch errors and do nothing, making failures invisible to users:
- Failed `getPlans()` shows "No plans yet" instead of error
- CSV export failure silently does nothing
- Delete plan failure closes modal silently
- Pause/resume toggle failure silently fails
- Equity curve fetch failure shows "Need 2+ snapshots"

## Findings
- `frontend/src/app/plans/page.tsx:40` — no .catch
- `frontend/src/app/plans/[id]/page.tsx:102` — `catch {}` empty
- `frontend/src/app/plans/page.tsx:53-59` — handleDelete no catch
- `frontend/src/app/plans/[id]/page.tsx:58-66` — handleToggleActive no catch
- `frontend/src/components/PlanEquityCurve.tsx:26` — swallows to empty array

## Proposed Solution
Add error state to each component, display inline:
```tsx
const [error, setError] = useState<string | null>(null);
getPlans()
  .then(setPlans)
  .catch(e => setError(e.message))
  .finally(() => setLoading(false));

if (error) return <ErrorBanner message={error} />;
```

## Acceptance Criteria
- [ ] All fetch errors surface to UI
- [ ] No empty catch blocks
- [ ] User can distinguish "no data" from "fetch failed"
