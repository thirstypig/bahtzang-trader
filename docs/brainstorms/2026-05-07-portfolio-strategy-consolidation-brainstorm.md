---
id: DOC-025
type: brainstorm
status: done
phase: null
owner: james
tags: [portfolios]
links: []
updated: 2026-07-22
---

# Portfolio + Strategy Consolidation

**Date:** 2026-05-07  
**Context:** Competitive positioning via asset coverage expansion + trading frequency optimization  
**Status:** Brainstorm complete — ready for planning

## What We're Building

Consolidate "Settings" and "Plans" into a unified **Portfolio** concept. Each portfolio encapsulates:
- Capital allocation (budget, virtual cash)
- Strategy rules (confidence thresholds, trading frequency limits, diversification constraints)
- Position tracking (what we own, when we touched each ticker)

Replace generic "Settings" terminology with domain-specific "Portfolio" and "Strategy" language.

## Why This Approach

**Problems we're solving:**
1. "Settings" is too vague — unclear that settings are per-portfolio, not global
2. "Plans" doesn't capture that each plan has its own *strategy*, not just allocation
3. No explicit rules preventing repetitive trading (whipsaw, over-concentration)
4. Strategy changes can be confusing — need clear indication when rules change mid-portfolio-life

**Benefits:**
- Clearer mental model: one portfolio = one strategy + one allocation
- Scoped customization: each portfolio can have different rules (e.g., conservative = longer cooldown, aggressive = shorter)
- Enables competitive expansion: strategies per asset class (equities, crypto, forex) become different portfolios
- Prevents "just holding cash" by enforcing trading discipline (diversification, frequency caps)

## Key Decisions (Locked)

| Decision | Rationale |
|----------|-----------|
| **Existing positions stay when rules change** | Don't force-close positions Claude already made. New rules apply prospectively. |
| **Rule changes flagged in UI/audit log** | Show user *when* rules changed so they can correlate with position performance. |
| **Per-ticker cooldown (24–48 hrs configurable)** | After trading a ticker, enforced wait before touching it again. Prevents whipsaw, enforces diversification. |
| **Max 5 trades/week per ticker** | Frequency cap to limit churn and slippage. |
| **No same action twice in a row (per ticker)** | Can't buy AAPL, then buy AAPL again immediately. Avoids doubling down on same signal. |
| **Consolidate Settings + Plans → Portfolios** | One concept = one allocation + one strategy, not two separate ideas. |

## Architecture

### Before
```
Settings (product-wide guardrails)
Plans (per-plan budgets + strategy somewhere?)
```

### After
```
Portfolios (named allocation + strategy rules, per portfolio)
├── Name (e.g., "Growth Equities")
├── Budget ($100)
├── Strategy
│   ├── Confidence threshold
│   ├── Per-ticker cooldown (24/48 hrs)
│   ├── Max trades/week
│   └── Other rules
└── Positions (current holdings + touch history)
```

### UI Changes
- `/settings` → eliminate
- `/plans` → `/portfolios`
- Inside each portfolio: "Strategy" or "Rules" tab where users configure cooldown, confidence, etc.

## Cooldown Configuration

Two options for the per-ticker cooldown setting:

**Option A: Slider (24–72 hours)**
- User sets cooldown duration per portfolio
- More granular control
- Default: 48 hours

**Option B: Preset buttons (Conservative/Balanced/Aggressive)**
- Conservative = 48 hrs
- Balanced = 24 hrs
- Aggressive = 12 hrs (or none)
- Simpler UX, less decision fatigue

**Recommendation:** Start with Option B (presets), add slider later if users request fine-tuning.

## Rule Changes & Position Safety

When a user changes strategy rules (e.g., cooldown from 24h → 48h):

1. **Existing positions unaffected** — touch-history clock doesn't reset
2. **Future decisions use new rules** — Claude respects new cooldown
3. **Audit log entry created** — timestamp, old rule, new rule, user
4. **Optional: In-app alert** — "Strategy rules changed at 2:30 PM. See audit log."

Example: Bought AAPL at 10 AM with 24h cooldown. At 2 PM, user changes to 48h. AAPL remains bought, and Claude won't touch it until 10 AM tomorrow (or 10 AM day after, depending on interpretation). Audit log shows the change.

---

## Resolved Questions

1. **Cooldown interpretation** — Cooldown measured from trade *decision* time (when Claude decided), not execution time. Decision timestamp is more meaningful for the signal perspective.

2. **Frequency cap scope** — "Max 5 trades/week per ticker" = **5 buys AND 5 sells** (up to 10 total actions per ticker per week). Allows active rebalancing while still capping churn.

3. **Default cooldown for new portfolios** — User chooses cooldown duration when creating a portfolio (no preset default). Maximizes flexibility and transparency.

## Deferred Questions

4. **Multi-asset support** — When we add crypto/forex (Phase G+), does each asset class get its own portfolio, or do we mix assets in one portfolio with different cooldowns per asset?
   - Out of scope for now, but architecture should allow it

---

## Success Criteria

When this is shipped:
- ✓ No product-wide "Settings" page (all strategy config is per-portfolio)
- ✓ `/portfolios` page shows list with strategy summary (e.g., "48h cooldown, 5/week limit")
- ✓ Trading frequency rules enforced by executor
- ✓ Rule changes visible in audit log
- ✓ Paper trading shows no repeated touches to same ticker within cooldown window

