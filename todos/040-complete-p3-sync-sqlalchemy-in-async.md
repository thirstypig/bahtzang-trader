---
status: complete
priority: p3
issue_id: "040"
tags: [code-review, performance, async]
dependencies: []
---

# Synchronous SQLAlchemy in Async Context

## Problem Statement

`check_guardrails()` runs synchronous DB queries (`db.query().count()`) that block the event loop when called from async `_execute_cycle()`.

**Found by:** Performance oracle (HIGH)

## Fix

Either wrap DB ops in `asyncio.to_thread()`, switch to async SQLAlchemy engine, or accept the blocking since `_cycle_lock` already serializes access.
