---
status: complete
priority: p1
issue_id: "025"
tags: [code-review, security, error-handling]
dependencies: []
---

# Exception Details Leaked in HTTP Error Responses

## Problem Statement

Multiple endpoints expose raw Python exception messages in HTTP error responses. These can contain API endpoint URLs, authentication error details, internal server paths, database connection strings, or SDK stack traces.

**Found by:** Python reviewer (P1), Security sentinel (H1, H2 HIGH)

## Findings

- `backend/app/routes/bot.py:27` — `detail=f"Trading cycle failed: {e}"` leaks run_cycle exceptions
- `backend/app/routes/portfolio.py:24` — `detail=f"Portfolio unavailable: {e}"` leaks broker exceptions
- `backend/app/auth.py:50` — `detail=f"Invalid token: {e}"` aids token-forging attacks
- Exceptions from Alpaca, Alpha Vantage, Anthropic SDKs may contain sensitive info
- Full exceptions are already logged server-side (good), but also sent to client (bad)

## Proposed Solutions

Return generic messages, keep server-side logging:

```python
# bot.py
raise HTTPException(status_code=500, detail="Trading cycle failed. Check server logs.")

# portfolio.py
raise HTTPException(status_code=503, detail="Portfolio temporarily unavailable.")

# auth.py
raise HTTPException(status_code=401, detail="Invalid token")
```

- **Effort:** Small (5 min per file)
- **Risk:** None

## Acceptance Criteria

- [ ] HTTP error responses contain no internal details
- [ ] Full exception details are still logged server-side
- [ ] Auth errors don't reveal why token verification failed

## Work Log

| Date | Action | Result |
|------|--------|--------|
| 2026-04-10 | Code review found issue | 2 agents flagged |
