---
status: pending
priority: p3
issue_id: "042"
tags: [code-review, security, cleanup]
dependencies: []
---

# Dead Schwab Credentials Still Required at Startup

## Problem Statement

`schwab_client.py` is still in the codebase (Alpaca is active broker). Schwab config fields in Pydantic `BaseSettings` require env vars at startup even though the code is unused.

**Found by:** Security sentinel (M5 MEDIUM)

## Fix

Make Schwab config fields optional with `str = ""` defaults, or remove `schwab_client.py` entirely.
