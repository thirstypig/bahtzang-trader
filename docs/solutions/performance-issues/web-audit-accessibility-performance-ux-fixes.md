---
title: "Comprehensive Web Audit: Accessibility, Performance & UX Fixes"
date: 2026-04-17
category: performance-issues
tags:
  - accessibility
  - performance
  - wcag
  - next-js
  - code-splitting
  - server-components
  - caching
  - n-plus-one
  - mobile-responsive
severity: high
components:
  - frontend (Next.js 14)
  - backend (FastAPI)
  - database (SQLAlchemy)
symptoms:
  - Recharts 312KB loaded on every page
  - All 19 pages were client components
  - Analytics fetched 500 trades with reasoning text (~5MB)
  - Backtest list N+1 query
  - Muted text contrast 2.46:1 (WCAG AA requires 4.5:1)
  - Horizontal overflow on mobile viewports
  - No error boundary, no custom 404, no loading states
  - No HTTP caching headers, no fetch timeout
root_cause_summary: >
  No performance or accessibility review had been performed. All pages
  defaulted to client components, heavy libraries loaded globally, no
  caching strategy, and no WCAG compliance checks.
---

## Problem

A comprehensive audit of bahtzang-trader revealed 20+ issues across accessibility, performance, and UX. The app functioned correctly but shipped unnecessary JavaScript, failed WCAG contrast requirements, lacked error handling infrastructure, and had no caching strategy.

### Key Symptoms

**Performance:**
- Recharts (312KB) bundled into shared chunk, loaded on every page even without charts
- All 19 pages marked `"use client"` — zero Server Components
- Analytics page fetched 500 trades with full `claude_reasoning` text (~5MB payload)
- Backtest list endpoint: N+1 query (1 extra DB query per backtest config)
- No HTTP `Cache-Control` headers on any backend endpoint
- No fetch timeout — frontend requests could hang indefinitely

**Accessibility:**
- Muted text (slate-400) on light backgrounds: contrast ratio 2.46:1 (WCAG AA requires 4.5:1)
- No skip-to-content link
- No `focus-visible` styles on buttons/links
- No `prefers-reduced-motion` support
- 15/16 sidebar links lacked accessible names when collapsed (icon-only)
- No `aria-current` on active navigation links

**UX:**
- Tooltip `w-64` (256px fixed width) caused horizontal overflow on mobile viewports
- Portfolio Summary values overlapped and were illegible on phones
- No error boundary, no custom 404 page, no loading.tsx route files
- 404 page text nearly invisible in dark mode

## Root Cause

No audit or review process existed. Pages were created as client components by default (copy-paste from existing pages). Heavy libraries were imported directly without code splitting. The backend had no caching middleware. Accessibility was never validated against WCAG standards.

## Solution

24 files changed, +364/-40 lines. PR #12 merged to main.

### Accessibility Fixes (12)

**1. Text contrast** — `globals.css`
```css
/* Before: slate-400, ratio 2.46:1 */
--text-muted: 148 163 184;
/* After: slate-500, ratio 4.6:1 */
--text-muted: 100 116 139;
```

**2. Reduced motion** — `globals.css`
```css
@media (prefers-reduced-motion: reduce) {
  *, ::before, ::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

**3. Global focus ring** — `globals.css`
```css
button:focus-visible, a:focus-visible,
select:focus-visible, [role="tab"]:focus-visible {
  outline: 2px solid rgb(var(--accent));
  outline-offset: 2px;
  border-radius: 4px;
}
```

**4. Tooltip overflow** — `Tip.tsx`
```tsx
// Added max-w constraint to prevent mobile overflow
className="w-64 max-w-[calc(100vw-2rem)] ..."
```

**5. Responsive Portfolio Summary** — `PortfolioCard.tsx`
```tsx
// Before: grid-cols-3 (values overlap on mobile)
// After: stacks on mobile, 3 columns on sm+
<div className="grid grid-cols-1 gap-4 sm:grid-cols-3 sm:gap-6">
```

**6. Skip-to-content link** — `providers.tsx`
```tsx
<a href="#main-content"
   className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 ...">
  Skip to main content
</a>
```

**7-9. Sidebar ARIA** — `Sidebar.tsx`, `ThemeToggle.tsx`, `providers.tsx`
- Added `aria-label` on collapsed nav links
- Added `aria-current="page"` on active link
- Added `focus-visible:ring-2` styles
- Changed mobile nav `<div>` to `<header>`
- Added `aria-label` on theme toggle

**10-12. Error handling** — new files
- `not-found.tsx`: Custom 404 with proper theme colors
- `error.tsx`: Error boundary with retry button
- `loading.tsx`: Root loading spinner

### Performance Fixes (7)

**1. Dynamic imports for Recharts** — 4 page files
```tsx
import dynamic from "next/dynamic";
const AllocationChart = dynamic(
  () => import("@/components/AllocationChart"),
  { ssr: false }
);
```
Applied to all 7 chart components across dashboard, analytics, plans, and plan detail pages.

**Result:** Dashboard 269KB -> 153KB (-43%), Analytics 272KB -> 153KB (-44%)

**2. Server Components** — `changelog/page.tsx`, `roadmap/page.tsx`, `CrossLink.tsx`
Removed `"use client"` directive. Replaced `useHashScroll()` hook with a tiny `<HashScroll />` client component that renders `null`.

**3. Lightweight trades endpoint** — `routes/trades.py`
```python
@router.get("/trades/summary")
def get_trades_summary(limit=500, db=..., user=...):
    """Excludes claude_reasoning — ~90% smaller payload."""
    trades = db.query(
        Trade.id, Trade.timestamp, Trade.ticker, Trade.action,
        Trade.quantity, Trade.price, Trade.confidence,
        Trade.guardrail_passed, Trade.executed,
    ).order_by(Trade.timestamp.desc()).limit(limit).all()
```
Analytics page switched from `getTrades(500)` to `getTradesSummary(500)`.

**4. Backtest N+1 fix** — `backtest/routes.py`
```python
# Before: N+1 (1 query per config)
for config in configs:
    result = db.query(BacktestResult).filter(...).first()

# After: batch load all results in 1 query
config_ids = [c.id for c in configs]
results = db.query(BacktestResult).filter(
    BacktestResult.config_id.in_(config_ids)
).all()
results_map = {r.config_id: r for r in results}
```

**5. HTTP caching** — `main.py` middleware
```python
@app.middleware("http")
async def add_cache_headers(request, call_next):
    response = await call_next(request)
    if request.method == "GET" and response.status_code == 200:
        if path.startswith("/earnings"):
            response.headers["Cache-Control"] = "private, max-age=3600"
        elif path.startswith("/portfolio/snapshots"):
            response.headers["Cache-Control"] = "private, max-age=300"
        elif path.startswith("/trades"):
            response.headers["Cache-Control"] = "private, max-age=60"
```

**6. Fetch timeout** — `api.ts`
```tsx
const res = await fetch(`${API}${path}`, {
  ...options,
  signal: options?.signal ?? AbortSignal.timeout(15000),
});
```

**7. Parallel plan detail fetches** — `plans/[id]/page.tsx`
Child components (`PlanPositions`, `PlanEquityCurve`) now mount during the parent's loading state, so all 3 API calls run in parallel instead of sequentially.

### Bundle Size Results

| Page | Before | After | Savings |
|------|--------|-------|---------|
| Dashboard | 269KB | 153KB | -43% |
| Analytics | 272KB | 153KB | -44% |
| Plans list | 260KB | 161KB | -38% |
| Plan detail | 258KB | 154KB | -40% |
| Changelog | 100KB | 97KB | Server Component |
| Roadmap | 90KB | 88KB | Server Component |

## Prevention: Checklist for New Features

### Before creating a page
- [ ] Start as Server Component (no `"use client"`) — add it only if you need hooks/events
- [ ] Heavy libraries (`recharts`, etc.) wrapped in `dynamic(() => import(...), { ssr: false })`
- [ ] Data fetching uses `getTradesSummary()` not `getTrades()` unless reasoning text is needed

### Before creating an API endpoint
- [ ] List endpoints have `limit` parameter (no unbounded queries)
- [ ] No N+1 patterns (use batch queries or `joinedload()`)
- [ ] `Cache-Control` header set in caching middleware

### Before merging
- [ ] `npx next build` output checked — page size reasonable
- [ ] Mobile viewport tested (375px minimum)
- [ ] Contrast ratios checked for any new text colors (4.5:1 minimum)
- [ ] Interactive elements have `focus-visible` styles
- [ ] Loading and error states exist for data-dependent views

## Related Documentation

- `docs/solutions/deployment-issues/railway-silent-deploy-failure-pandas-ta.md` — Railway deploy troubleshooting
- `docs/solutions/integration-issues/feature-module-isolation-pattern.md` — Feature module architecture
- `docs/solutions/integration-issues/supabase-es256-jwt-migration.md` — Auth setup
