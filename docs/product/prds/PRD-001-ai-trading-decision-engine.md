---
id: PRD-001
type: prd
status: draft
phase: G
owner: james
tags: [trading-pipeline, risk, phase-g]
links: [DOC-001]
updated: 2026-07-22
---

# PRD-001 — AI Trading Decision Engine

<!-- WORKED SKELETON. Structure is final; content is filled by the archaeology pass,
     which reconstructs each section from the code. Delete these guidance comments as
     you fill them in.

     HONESTY TAGGING — every claim in this doc carries one of:
       [intended]  a deliberate up-front decision (say why you believe that)
       [inferred]  reconstructed from the code — a reasonable read, not a known fact
       [unknown]   the code cannot tell us. Ask James. Do NOT invent it.
     A section full of [unknown] is a success. Those are the questions worth asking. -->

**Feature:** Claude decides buy / sell / hold for each portfolio on a live paper account.
**Backed by:** `backend/app/claude_brain.py`, `backend/app/plans/executor.py`

---

## 1. Problem statement

<!-- What is broken, and for whom? Be concrete about the "before" state. This is a
     personal experiment with one user — say so rather than inventing a user segment. -->

## 2. Strategic rationale

<!-- Why does this exist at all? Why was it worth building? Tie it to the core value:
     can an LLM make defensible trading decisions given portfolio + market context?
     Why build it rather than use an off-the-shelf rules engine? -->

## 3. User story

<!-- As a [role], I want ... so that ...
     Note the real role here is operator/experimenter, not "trader" or "customer". -->

## 4. Assumptions

<!-- What had to be TRUE for this to be worth building? Name the bets the build made
     implicitly, even if never stated out loud. Examples worth examining:
       - that an LLM's reasoning beats a fixed rule set on this task
       - that daily decision cadence is frequent enough to capture the edge
       - that natural-language reasoning is worth its cost and latency
     Mark each [intended] / [inferred] / [unknown]. -->

## 5. Impact & KPIs

<!-- SPLIT INTO TWO. Do not blur them. -->

### (a) What the metric SHOULD be

<!-- The bet you would have made. What would prove this feature works? -->

### (b) What we can measure TODAY

**Decision *quality* is not instrumented.** [inferred, HIGH confidence]

The `trades` table records what was decided — ticker, action, quantity, price,
`claude_reasoning`, `confidence`, whether it executed. So we can measure *activity*
(trade count, execution rate, block reasons) and *portfolio outcome* (`plan_snapshots`
P&L, once the pricing bug was fixed on 2026-07-22).

What nothing measures: **whether a given decision was good.** There is no field linking a
decision to its realised outcome, no attribution of P&L back to the reasoning that caused
it, no baseline (what would buy-and-hold, or a coin flip, have returned over the same
window?). The engine's core bet — that Claude's judgment beats a rule set — has never been
measured, because the measurement does not exist.

This is [unknown] territory that the code *can* eventually answer but currently does not:
the raw material (per-trade reasoning + confidence + outcome) is captured; nothing joins
it. See RISK-007 in the risks register.

## 6. Technical notes

<!-- How it is ACTUALLY built, read from the code. Cover: the gather → decide → validate
     → act → log pipeline, the three decision modes, timeouts, and what gets persisted
     on every cycle including holds and blocked trades. -->

## 7. AI implementation notes

<!-- Model id, prompt strategy (CSV context blocks), timeout, and cost per call.
     Cost per call: [unknown] unless measured — do not estimate it as fact.
     Note the retired-model-id outage as evidence of a real operational risk here. -->

## 8. Testing plan

<!-- What tests exist TODAY vs what should exist. Be specific about coverage gaps —
     e.g. failures that only appear against Postgres and pass under SQLite. -->

## 9. What we'd do differently

<!-- The hindsight section. This is where the exercise pays off — be candid.
     Fair game: whether decision quality was ever measurable, whether the risk
     controls matched the ambition of the decision layer, and what was built
     around this feature before this feature was proven. -->
