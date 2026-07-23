---
id: ADR-001
type: adr
status: locked
phase: null
owner: james
tags: [trading-pipeline, portfolios, backend]
links: [PRD-001, DOC-007]
updated: 2026-07-22
---

# ADR-001 — Portfolio-only execution model

<!-- ADRs are for BIG decisions that are costly to reverse: things that, if undone,
     would ripple through many files or invalidate stored data. Small calls — a library
     choice, a naming convention, a threshold tweak — go in decision-log.md instead.
     If you are unsure which it is, ask: "would reversing this be a project, or an
     afternoon?" A project means ADR.

     Every claim below is tagged [intended] / [inferred] / [unknown]. -->

**Status:** locked · **Reversing this is a project, not an afternoon.**

## Context

The system originally executed trades through a single global path — `trade_executor.py`,
a global guardrails singleton, and one account-wide kill switch. **[inferred]** from the
commit trail: those artifacts existed and were deliberately removed.

The requirement that broke that model: running several strategies at once, each with its
own budget, trading goal, risk profile, and stop button, against **one real broker
account**. A single global executor cannot express "this strategy is paused but that one
is not," and it cannot stop two strategies from spending the same dollar twice.

**[unknown]** — whether multi-strategy was an original goal or emerged later. The commit
order suggests the global path came first and was refactored away, but that does not tell
us what was intended at the start. Worth confirming.

## Decision

**Every trade runs through a Portfolio.** There is no global execution path.

A Portfolio is a virtual sub-account holding its own budget, virtual cash, goal, risk
profile, and `is_active` kill switch. The scheduler calls `run_all_plans()`; there is no
other way in. **[intended]** — recorded in `CLAUDE.md` under decisions not to be
re-litigated, which is a deliberate statement, not an artifact.

Evidence in the history:

| Commit | What it did |
|---|---|
| `819a89d` | Cut the scheduler over to portfolio-only; dropped the global trader |
| `f79cc89` | Dropped the global guardrails singleton |
| `4e4858e` | Replaced the global kill switch with a per-portfolio one |
| `2951f9c` | Consolidation PR (#16) |
| `542068f` | Backfilled orphan trades onto a default portfolio |

That last one matters: existing trade rows had to be reassigned to a portfolio. Data was
migrated to fit the model, which is a large part of why reversing it is expensive.

## Consequences

**Good**

- Each strategy gets an independent kill switch — one can be halted without stopping the rest.
- Budgets are enforced per strategy, and `SUM(budgets) <= real equity` is checkable.
- Every trade has a portfolio owner, so P&L is attributable rather than pooled.

**Costly / accepted**

- **Concurrency became a real problem.** Several portfolios sharing one account can
  double-spend. This required per-portfolio `asyncio` locks *and* `pg_advisory_xact_lock`
  for cross-process budget validation — machinery a single global trader never needed.
- **Sells need theft protection.** A portfolio must not sell a position another portfolio
  owns, so sell validation checks *virtual* positions rather than the broker's.
- **Virtual accounting is now load-bearing.** Virtual cash and cost basis are computed
  from the trade ledger, not read from the broker. **[inferred]** — this is what makes
  the model work, and also what makes ledger bugs expensive.
- **Data migration already happened** (`542068f`), so reverting means migrating back.

**Unresolved**

- **[unknown]** — whether the circuit breaker deactivating *every* portfolio at RED is
  the intended blast radius, or a convenience carried over from the global kill switch.
  It is the one place where global behaviour survived the refactor.
