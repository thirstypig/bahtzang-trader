---
status: complete
priority: p2
issue_id: "030"
tags: [code-review, security, ai-prompting]
dependencies: []
---

# Prompt Injection Surface via Guardrails Config

## Problem Statement

The full `guardrails_config` dict is serialized to JSON and included in Claude's prompt without key whitelisting. Extra keys injected into `guardrails.json` would appear in Claude's input.

**Found by:** Security sentinel (H3 HIGH)

## Findings

- `backend/app/claude_brain.py:121` — `"guardrails": guardrails_config` passes entire dict
- `load_guardrails()` reads whatever is in JSON file without schema validation
- Arbitrary keys (e.g., `"__override_system_prompt"`) would be passed to Claude
- Pydantic validates API input but NOT loaded file contents
- Mitigated by: `check_guardrails()` independently validates Claude's output

## Proposed Solutions

Whitelist keys before passing to Claude:

```python
ALLOWED_CONFIG_KEYS = {"risk_profile", "trading_goal", "max_total_invested",
    "max_single_trade_size", "stop_loss_threshold", "daily_order_limit",
    "min_confidence", "max_positions", "kill_switch"}
safe_config = {k: v for k, v in guardrails_config.items() if k in ALLOWED_CONFIG_KEYS}
```

- **Effort:** Small (~10 lines)
- **Risk:** None
