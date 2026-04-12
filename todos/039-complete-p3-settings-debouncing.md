---
status: pending
priority: p3
issue_id: "039"
tags: [code-review, frontend, performance]
dependencies: []
---

# No Request Debouncing on Settings Page

## Problem Statement

Every goal/frequency/risk click fires an immediate API call. Rapid clicks fire multiple sequential requests, compounding the backend race condition.

**Found by:** Performance oracle (MODERATE)

## Fix

Batch changes locally and save with a single API call, or add AbortController-based debouncing.
