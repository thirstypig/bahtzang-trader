---
status: pending
priority: p2
issue_id: "095"
tags: [code-review, frontend, duplication]
dependencies: []
---

# GOAL_LABELS Defined Three Times Across Frontend

## Problem Statement

Three separate `GOAL_LABELS` maps exist with different shapes:
1. `plans/[id]/page.tsx:17` — `Record<TradingGoal, string>` (emoji+label combined)
2. `plans/page.tsx:17` — `Record<TradingGoal, { label, icon }>` (structured)
3. `components/BotStatusBanner.tsx:8` — `Record<string, string>` (loses type safety)

Adding a new `TradingGoal` variant requires updating all three. The BotStatusBanner version also loses type safety by using `Record<string, string>`.

## Findings

- **Source:** TypeScript Reviewer, Code Simplicity Reviewer (confirmed independently)

## Proposed Solutions

Create one canonical `GOAL_CONFIG` in `lib/constants.ts` with `{ label, icon }` shape. Derive simpler forms where needed:
```typescript
// lib/constants.ts
export const GOAL_CONFIG: Record<TradingGoal, { label: string; icon: string }> = { ... };
```

- **Effort:** Small
- **Risk:** Low

## Acceptance Criteria

- [ ] Single source of truth for goal labels/icons
- [ ] All three files import from the shared constant
- [ ] BotStatusBanner uses `TradingGoal` type instead of `string`

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-04-18 | Created from TypeScript reviewer + simplicity reviewer | |
