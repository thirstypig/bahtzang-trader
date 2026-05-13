# Decision Modes

Each portfolio independently controls which system makes its trade decisions. The `decision_mode` field on a Portfolio can be set from the Decision Engine page (`/portfolios/[id]/strategy`).

---

## Three Modes

### 1. Claude decides (`claude_decides`)

Claude Sonnet reads the full market context — positions, quotes, technicals, news, earnings calendar, sector rotation — and generates each trade decision from scratch.

**Use when:** You want the AI to weigh all signals together, adapt to context, and reason through ambiguous situations.

**Cost:** One Claude API call per trading cycle, regardless of how many tickers are in the portfolio.

**Reproducibility:** Non-deterministic. The same market data can produce different decisions on different runs.

**Audit:** `claude_reasoning` field on each Trade record contains Claude's full reasoning text.

---

### 2. Rules decide (`rules_decide`)

A deterministic strategy (e.g., SMA Crossover, Dual Momentum) generates all decisions. Claude is never called.

**Use when:** You want cheap, fast, repeatable execution. Ideal for strategies you've already backtested and want to run live without introducing AI variance.

**Cost:** Zero Claude API calls. Only the strategy's signal generation logic runs.

**Reproducibility:** Exact. A `rules_decide` portfolio running SMA Crossover with the same parameters will produce the same decisions as a backtest using that strategy — the code path is literally the same `generate_signals()` method.

**Audit:** `claude_reasoning` contains the strategy's signal reasoning. `rules_recommendation` is `NULL` (no oversight layer).

**Backtest equivalence:** This is the only mode that exactly replicates a backtest. `claude_decides` and `rules_with_claude_oversight` both introduce non-determinism that cannot be backtested.

---

### 3. Rules + Claude oversight (`rules_with_claude_oversight`)

The strategy generates a recommendation for each decision. Claude then reviews that specific recommendation and either confirms it or overrides it with a different action.

**Use when:** You want the rules-based signal as a disciplined starting point, but you want Claude to catch obvious exceptions (e.g., the strategy signals a buy right before an earnings announcement).

**Cost:** One Claude API call per recommended trade (not per cycle — only called for non-hold signals). Costs more than `rules_decide` but less than a full `claude_decides` cycle when the strategy holds frequently.

**Reproducibility:** Partially. The strategy's initial signal is deterministic. Claude's review is not.

**Audit:** The strategy's original signal is stored in `rules_recommendation` (JSON) on the Trade record. The final action reflects Claude's decision. Divergence (override) is flagged on the Oversight Activity page.

**Fail-closed:** If Claude's review call times out or returns malformed JSON, the strategy's original signal is used as-is (confirmed). This prevents oversight failures from blocking valid trades.

---

## Oversight Activity

For portfolios in `rules_with_claude_oversight` mode, the Oversight Activity page (`/portfolios/[id]/oversight`) shows:

- **Summary stats:** total decisions reviewed, confirmed count/%, overridden count/%
- **Per-decision records:** the strategy's original signal alongside the final decision, with a visual indicator for overrides

Shadow execution tracking (running the rules-only path in parallel to measure override P&L impact vs. rules-only P&L) is a future enhancement — not currently implemented.

---

## Choosing a Mode

| Goal | Mode |
|------|------|
| AI-driven, adapts to context | `claude_decides` |
| Exactly replicate a backtest live | `rules_decide` |
| Rules discipline + AI safety net | `rules_with_claude_oversight` |
| Lowest API cost | `rules_decide` |
| Highest auditability | `rules_decide` or `rules_with_claude_oversight` |

---

## Changing Modes

Mode changes take effect on the **next trading cycle**. Existing positions are not closed, and past trades are not modified. A confirmation modal on the Decision Engine page reminds you of this.

Mode changes are logged in `PortfolioStrategyAudit` with the old and new config snapshot.
