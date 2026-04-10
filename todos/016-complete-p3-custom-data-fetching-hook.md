---
status: pending
priority: p3
issue_id: "016"
tags: [code-review, quality, duplication]
dependencies: []
---

# Create Custom Authenticated Data-Fetching Hook

## Problem Statement

Every page repeats the same pattern: `useAuth` + `useState` + `useEffect(if !user return; fetch.then.finally)`. Error handling is inconsistent across pages -- some catch errors, some don't. This results in ~15 duplicated lines per page and fragile, divergent data-fetching logic.

**Found by:** Code review

## Findings

- 5 pages in the frontend repeat the same data-fetching boilerplate
- Each page independently implements: auth check, loading state, fetch call, and cleanup
- Some pages catch fetch errors and display them; others silently swallow errors
- No centralized retry, caching, or error-reporting strategy

## Proposed Solutions

Create a `useAuthenticatedQuery<T>(fetcher)` hook that encapsulates the auth-gated fetch pattern. This eliminates ~15 lines per page and standardizes error handling across all pages.

## Technical Details

**Affected files:** 5 page components in `frontend/src/app/`

**Effort:** Medium

## Acceptance Criteria

- [ ] A `useAuthenticatedQuery<T>` hook exists (e.g., in `frontend/src/hooks/`)
- [ ] The hook handles: auth gating, loading state, error state, and data state
- [ ] All 5 pages are refactored to use the new hook
- [ ] Error handling is consistent: all fetch failures are caught and surfaced
- [ ] Existing page behavior is unchanged from the user's perspective
