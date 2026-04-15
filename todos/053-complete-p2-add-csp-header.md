---
status: complete
priority: p2
issue_id: "053"
tags: [code-review, security]
dependencies: []
---

# Add Content-Security-Policy header

## Problem Statement
Security headers include HSTS, X-Frame-Options, etc. but no CSP. The inline theme script in layout.tsx would benefit from hash-based CSP for defense-in-depth.

## Findings
- `frontend/next.config.mjs` — security headers configured but CSP is missing

## Proposed Solutions
Add CSP header with `script-src 'self' 'sha256-<hash>'` for the inline theme script. Add `style-src`, `img-src`, `default-src` directives.

```js
{
  key: "Content-Security-Policy",
  value: "default-src 'self'; script-src 'self' 'sha256-<computed-hash>'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self'; connect-src 'self' https://api.example.com;"
}
```

Compute the SHA-256 hash of the inline theme script and substitute it in the policy.

## Acceptance Criteria
- [ ] CSP header present in response headers
- [ ] Inline theme script still executes
- [ ] No CSP violations in console
