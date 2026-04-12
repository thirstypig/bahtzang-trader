---
status: pending
priority: p3
issue_id: "043"
tags: [code-review, security, observability]
dependencies: ["021"]
---

# No Audit Trail for Guardrail Changes

## Problem Statement

Guardrail changes (risk profile switches, goal changes, kill switch activation) are not logged with who, what, or when. No forensic trail after incidents.

**Found by:** Security sentinel (L1 LOW)

## Fix

Add audit log table when guardrails move to DB (todo 021). Log each change with timestamp, user email, old value, new value.
