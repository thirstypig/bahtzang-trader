---
status: complete
priority: p3
issue_id: "041"
tags: [code-review, performance, cost]
dependencies: []
---

# json.dumps(indent=2) Wastes Tokens in Claude Prompt

## Problem Statement

`json.dumps(payload, indent=2)` adds ~200-400 extra whitespace tokens per Claude API call.

**Found by:** Performance oracle (LOW)

## Fix

Remove `indent=2` from `claude_brain.py:132`. Claude parses compact JSON equally well.
