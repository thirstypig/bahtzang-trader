---
status: complete
priority: p3
issue_id: "044"
tags: [code-review, observability, logging]
dependencies: []
---

# APScheduler Error Handler Swallows Traceback

## Problem Statement

`_scheduled_cycle()` catches exceptions with `logger.error()` instead of `logger.exception()`, losing the full traceback.

**Found by:** Performance oracle (LOW)

## Fix

Change `logger.error()` to `logger.exception()` in `scheduler.py:33-34`.
