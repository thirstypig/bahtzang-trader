---
status: pending
priority: p3
issue_id: "079"
tags: [code-review, typescript, plans]
dependencies: []
---

# TypeScript union types defined but not used

## Problem Statement
The `TradingGoal`, risk profile, and frequency unions are defined in types.ts but the plans UI uses plain `string`. The compile-time safety net is thrown away.

## Findings
- `frontend/src/app/plans/new/page.tsx:35-36` — `useState("moderate")` infers string
- `frontend/src/app/plans/page.tsx:15` — `Record<string, ...>` should be `Record<TradingGoal, ...>`
- `frontend/src/lib/api.ts:295` — `createPlan(trading_goal: string)` should be TradingGoal

## Proposed Solution
```tsx
type RiskProfile = "conservative" | "moderate" | "aggressive";
type Frequency = "1x" | "3x" | "5x";

const [risk, setRisk] = useState<RiskProfile>("moderate");
const [freq, setFreq] = useState<Frequency>("1x");
```

## Acceptance Criteria
- [ ] All goal/risk/frequency fields use their union types
- [ ] Adding a new value forces exhaustiveness errors
