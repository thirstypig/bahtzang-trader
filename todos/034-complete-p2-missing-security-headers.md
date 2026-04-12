---
status: pending
priority: p2
issue_id: "034"
tags: [code-review, security, frontend]
dependencies: []
---

# Missing Security Headers (CSP, X-Frame-Options, etc.)

## Problem Statement

The Next.js config only sets HSTS. Missing: Content-Security-Policy, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy.

**Found by:** Security sentinel (M1 MEDIUM)

## Findings

- `frontend/next.config.mjs` — Only `Strict-Transport-Security` configured
- No CSP = no defense against injected scripts
- No X-Frame-Options = clickjacking risk
- Backend sets no security headers at all

## Proposed Solutions

Add headers in `next.config.mjs`:
```js
{ key: "X-Frame-Options", value: "DENY" },
{ key: "X-Content-Type-Options", value: "nosniff" },
{ key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
{ key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
```

- **Effort:** Small (~10 lines)
- **Risk:** None
