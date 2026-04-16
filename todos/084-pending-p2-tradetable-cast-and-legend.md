---
status: pending
priority: p2
issue_id: "084"
tags: [code-review, typescript, plans, regression]
dependencies: []
---

# Plan detail: TradeTable cast hides PlanTrade fields + legend is a lie

## Problem Statement
Fix 066 replaced the inline trade table with `<TradeTable trades={trades as Trade[]} />`. Two issues:

1. **`as Trade[]` cast hides fields**: PlanTrade has `virtual_cash_before`, `virtual_cash_after`, `plan_id` — not shown in TradeTable. The cast is redundant (already typed as Trade[]) and misleading (hides that plan-specific data is lost).

2. **Legend is now a lie**: The plan detail page still shows a status legend ("Executed / Hold / Blocked" with colored dots) but TradeTable doesn't render dots — it has its own action badges. Users see a legend that doesn't match the table.

3. **Features lost**: The previous inline table may have had plan-specific columns (cash before/after trade) that are now invisible.

## Findings
- `frontend/src/app/plans/[id]/page.tsx:246` — `<TradeTable trades={trades as Trade[]} />`
- `frontend/src/app/plans/[id]/page.tsx:226-239` — outdated status legend
- `frontend/src/components/TradeTable.tsx` — doesn't show virtual_cash_before/after

## Proposed Solution

Option A: Drop the cast, remove the outdated legend.
Option B: Extend TradeTable to optionally show virtual_cash columns when the trade is a PlanTrade.
Option C: Keep a slimmer custom table on plan detail page with the plan-specific fields.

Recommend Option A for now, then decide about option B/C later based on actual user need.

## Acceptance Criteria
- [ ] Remove redundant `as Trade[]` cast
- [ ] Remove or update the status legend to match actual TradeTable rendering
- [ ] Document (or restore) whether virtual_cash display is desired
