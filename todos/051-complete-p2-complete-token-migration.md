---
status: pending
priority: p2
issue_id: "051"
tags: [code-review, design-system, theme]
dependencies: []
---

# Complete semantic token migration (38 remaining hardcoded colors)

## Problem Statement
11 zinc references, 9 text-emerald-400, 12 focus:emerald, 4 settings emerald card styles remain hardcoded across 11 active files. Light mode will look broken where dark-palette colors are hardcoded.

## Findings
- `todos/page.tsx` — hardcoded zinc and emerald colors
- `backtest/page.tsx` — hardcoded zinc and emerald colors
- `settings/page.tsx` — hardcoded emerald card styles
- `earnings/page.tsx` — hardcoded zinc and emerald colors
- `status/page.tsx` — hardcoded zinc and emerald colors
- `roadmap/page.tsx` — hardcoded zinc and emerald colors
- `audit-log/page.tsx` — hardcoded zinc and emerald colors
- `changelog/page.tsx` — hardcoded zinc and emerald colors
- `concepts/page.tsx` — hardcoded zinc and emerald colors
- `BotStatusBanner.tsx` — hardcoded zinc and emerald colors

## Proposed Solutions
Replace hardcoded values with semantic tokens:

- `bg-zinc-500` -> `bg-muted`
- `placeholder-zinc-*` -> `placeholder-muted`
- `text-emerald-400` -> `text-accent`
- `focus:border-emerald-*` -> `focus:border-accent`
- `hover:ring-zinc-*` -> `hover:ring-border-strong`

Add `--accent-strong` token for button colors if needed.

## Acceptance Criteria
- [ ] Zero hardcoded zinc-* or emerald-400 in active page/component files (except brand button backgrounds)
- [ ] Light mode renders correctly on all pages
