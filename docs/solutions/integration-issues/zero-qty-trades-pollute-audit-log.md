---
id: DOC-045
type: solution
status: active
phase: null
owner: james
tags: [trading-pipeline]
links: []
updated: 2026-07-22
severity: medium
---

# Zero-quantity trades pollute audit log — coerce-before-validate fix

## Symptoms

- Audit log query showed dominant block reason was `Trade value $0.00 below $1 minimum`:
  - 27 blocks today, 10–19 every prior day
  - Every other block reason combined: ~30 over 14 days
  - The "Trade value $0" message hides what Claude was actually trying to do
- Real strategy/cash blocks (e.g., `Insufficient plan cash`) were buried in the noise
- Looked like a guardrail tuning problem at first glance — was actually a data-hygiene problem

## Investigation Steps

1. **Pulled the audit log** via Supabase SQL editor:

   ```sql
   SELECT guardrail_block_reason, COUNT(*) AS blocks, DATE_TRUNC('day', timestamp) AS day
   FROM trades
   WHERE guardrail_passed = false
     AND timestamp > NOW() - INTERVAL '14 days'
   GROUP BY guardrail_block_reason, day
   ORDER BY day DESC, blocks DESC;
   ```

   Output showed `Trade value $0.00 below $1 minimum` accounting for ~82% of blocks — a number high enough to indicate a *systemic* issue rather than a normal-trading edge case.

2. **Grep'd the message** to find the source:

   ```bash
   grep -nE "below.*minimum|< \$1" backend/app/
   ```

   Hit `backend/app/plans/executor.py:222`:

   ```python
   elif trade_value < 1.0:
       passed = False
       block_reason = f"Trade value $${trade_value:.2f} below $1 minimum"
   ```

3. **Traced backwards** for how `trade_value = 0` could happen:

   ```python
   trade_value = (price or 0) * decision.get("quantity", 0)
   ```

   Two paths to zero:
   - `quantity = 0` from Claude (or parser default)
   - `price = 0` from a failed price lookup

4. **Confirmed Claude's behavior**: looked at `backend/app/claude_brain.py` line 231:

   ```python
   "quantity": d.get("quantity", 0),
   ```

   If Claude omits `quantity` (e.g., when proposing a hold or when its JSON output is malformed), the parser defaults to 0. If `action` is also `"buy"` or `"sell"` for any reason, the result is a structurally-buy, semantically-hold decision that ends up at validation.

## Root Cause

Two-step interaction between Claude and our parser:

1. **Claude sometimes returns `{action: "buy", quantity: 0}`** when it's hedging or unclear. Semantically this means "hold," but structurally it's a buy with zero shares.
2. **The parser default fills `quantity=0`** if Claude omits the field, even when `action` is buy/sell. This compounds (1).

Validation is not at fault — `Trade value < $1` is a *correct* check. It's just receiving inputs that should never have reached it. The bug is upstream: zero-quantity buys/sells should be normalized to holds before they hit validation, both for log clarity and because there's no real intent behind a $0 trade.

The same root cause affected `app/trade_executor.py` (global Claude pipeline) — both executors call the same `claude_brain.get_trade_decision`, both inherit the parser default.

## Solution

### 1. Coerce zero-value buys/sells to holds *before* validation

Patched the per-decision loop in **both** executors:

```python
# Coerce zero-value buys/sells to holds BEFORE validation. Claude
# sometimes returns {"action": "buy", "quantity": 0} (semantically a
# hold) and our parser default also fills in quantity=0 if Claude
# omits it. Either way, sending these to guardrails just produces
# "$0.00 below $1 minimum" noise in the audit log without revealing
# any real intent. Surface as a hold with a clear reason instead.
if decision.get("action") in ("buy", "sell") and (decision.get("quantity") or 0) <= 0:
    logger.info("Coercing %s with qty=%s to hold",
                decision.get("action"), decision.get("quantity"))
    decision["action"] = "hold"
    decision["quantity"] = 0
    decision["reasoning"] = (
        f"{decision.get('reasoning', '')} "
        f"[Coerced to hold — Claude returned qty={decision.get('quantity', 0)}]"
    ).strip()
```

### 2. Same coercion for failed price lookups

If `price` came back 0 or `None` from the broker quote API:

```python
if not price or price <= 0:
    logger.warning("Coercing %s %s to hold — price=%s",
                   decision["action"], decision["ticker"], price)
    decision["action"] = "hold"
    decision["quantity"] = 0
    decision["reasoning"] = (
        f"{decision.get('reasoning', '')} "
        f"[Coerced to hold — price lookup failed for {decision['ticker']}]"
    ).strip()
    price = None
```

### 3. Audit trail preservation

Critical design decision: don't *drop* the decision, *coerce and log it*. The reasoning field gets a `[Coerced to hold — …]` suffix so the audit trail still records Claude's original intent. Future debugging of "why did the bot hold so much?" can grep for "Coerced" and find these cases.

## Tests

`backend/tests/test_zero_qty_coercion.py` (13 cases):

- 7 quantity-coercion: buy/sell with `qty 0`, negative, `None`, fractional pass-through, hold unchanged
- 5 price-coercion: zero/None/negative price → hold, valid price pass-through, hold-with-zero-price unchanged
- 1 plan-executor integration test: stubs `claude_brain.get_trade_decision`, asserts `cash_available + total_invested + orders_used_today` are computed and threaded through correctly

## Prevention

### Don't use defaults that silently coerce semantics

The parser default `quantity=0` was the load-bearing mistake. A better contract:

```python
# parser
"quantity": d.get("quantity"),  # None if missing — caller must handle
```

Then any caller who treats `None` as "buy zero" gets a TypeError instead of silent zero-trade pollution. We didn't change the parser this round (it's used in many places), but flagging for future cleanup.

### Audit-log queries are the canonical "why isn't X working" signal

The 30-minute fix arrived because we asked the right question first: *what are the actual block reasons?* Two months of "the bot isn't trading" without that data would have been guesswork. Pattern: when production behavior is wrong, query the audit log before changing code.

### Coerce inputs at boundaries, validate in the middle

The pattern here — normalize at the top of the pipeline, then validate — is broadly useful for any system that takes structured input from an external source (LLM, API, user form). Validation messages are clearer when the inputs are sane; debugging is easier when the audit log isn't full of edge-case noise.

## Related

- `integration-issues/feature-module-isolation-pattern.md` — the plan executor and main trade executor live in different modules but call the same Claude function. Bugs in shared-but-separate paths often need the same fix in both places (this one did).

## When this might recur

- Anywhere you `dict.get("field", default)` where the default has semantic meaning. If the default is a "valid value" (like `0` or `""`) instead of `None`, callers can't distinguish "field was missing" from "field was 0." Use `None` as the default sentinel, then coerce explicitly.
- Whenever a new code path adds an LLM-input → validation pipeline. The LLM will eventually emit structurally-valid-but-semantically-empty outputs; plan for it.
- After any refactor that changes how Claude's `quantity` field flows through the executor — re-verify the coercion is still in place.
