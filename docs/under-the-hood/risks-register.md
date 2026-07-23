---
id: DOC-017
type: risk
status: active
phase: null
owner: james
tags: [risk, trading-pipeline, testing]
links: [PRD-001, ADR-001, DOC-010]
updated: 2026-07-22
---

# Risks register

Running list of risks and open questions. Each carries a `RISK-###` id, a status, and an
owner. A risk with no owner is not being managed — it is being hoped about.

**Status:** `open` · `mitigating` · `accepted` · `closed`
**Severity:** how bad if it happens · **Likelihood:** how probable

> The entries below were seeded from the 2026-07-22 diagnostic session and are grounded
> in observed behaviour, not speculation. **Severity and likelihood ratings are my
> assessment and need your sign-off** — you own the risk appetite here, not me.

## Open risks

### RISK-001 — The stop-loss is not enforced anywhere

| | |
|---|---|
| **Status** | open |
| **Owner** | james |
| **Severity** | high |
| **Likelihood** | occurred |

`stop_loss_threshold` exists only as prompt text in `claude_brain.py` — it is a sentence
asking the model to sell, evaluated once per day at the 3:30 PM cycle. There is no check
in the executor or guardrails.

**Evidence:** 13 closed round-trips realised losses of **-10% to -24%** against a
nominal 5% stop (TER -23.7%, LRCX -14.5%, INTC -13.8%). Expectancy across those trades
was approximately **-$58 per trade**.

**Mitigation under design:** broker-held stops attached at entry, ATR-sized, with a daily
trailing ratchet. Designed 2026-07-22, not yet built.

---

### RISK-002 — Missing data can silently become a number

| | |
|---|---|
| **Status** | mitigating |
| **Owner** | james |
| **Severity** | high |
| **Likelihood** | occurred |

A failed price lookup defaulted to `0`, making "unknown" indistinguishable from
"worthless". Daily snapshots reported **-40.8%** on a portfolio that was actually down
**7.5%** — errors up to $4,156 in a single day.

**Fixed** in snapshots (Alpaca-primary pricing, bounded carry-forward, refuse-to-write
when unpriceable) and the history was rebuilt. **Still open as a class of risk:** other
code paths may hold the same `.get(key, 0)` pattern. Nobody has audited for it.

---

### RISK-003 — Silent failure is the default failure mode

| | |
|---|---|
| **Status** | open |
| **Owner** | james |
| **Severity** | high |
| **Likelihood** | occurred |

The system can stop working entirely without anyone noticing. A retired model id caused
**13 consecutive days of zero trades**; the scheduler ran fine, and every cycle died
before the logging step. It was found by manual inspection, not by an alert.

**Gap:** nothing watches for "expected activity did not happen." A cycle that produces no
rows is indistinguishable from a quiet market.

---

### RISK-004 — The test suite passes against a database we do not use

| | |
|---|---|
| **Status** | open |
| **Owner** | james |
| **Severity** | medium |
| **Likelihood** | occurred |

Tests run on SQLite; production is Postgres. SQLite accepted a `numpy.float64` that
crashed Postgres in production — the full suite was green throughout.

**Related:** the `pandas_ta` accessor is broken under the local Python build, so indicator
tests mock the computation and never exercise the real path.

---

### RISK-005 — Concentration masquerading as diversification

| | |
|---|---|
| **Status** | open |
| **Owner** | james |
| **Severity** | medium |
| **Likelihood** | occurred |

**10 of 12** names traded in Test 5 were semiconductors or storage. A momentum screener
naturally selects correlated names, so five open positions behaved as one leveraged bet
and drew down together.

**Mitigation under design:** portfolio heat cap plus a per-sector limit. Not built.

## Open questions

| id | Question | Owner | Status |
|---|---|---|---|
| RISK-006 | *Answered — see RISK-008.* Circuit-breaker blast radius is intended (documented in code), but wide. | james | closed |
| RISK-007 | Is decision quality instrumented at all? Nothing appears to measure whether Claude's calls were good. | james | open |

### RISK-008 — Circuit breaker RED deactivates all portfolios, not just the offender

| | |
|---|---|
| **Status** | accepted (for now) |
| **Owner** | james |
| **Severity** | low today · medium under multi-portfolio |
| **Likelihood** | latent |

When the account-wide breaker hits RED, `executor.py:770` deactivates **every** active
portfolio and requires a manual reset. This is **intended** — the code documents it as a
deliberate "halt everything fast in a panic" choice — but the breaker measures the
**pooled** Alpaca account, so one portfolio's drawdown can freeze healthy, uncorrelated
portfolios until a human re-enables them.

**Why it is accepted, not fixed:** only one portfolio (Test 5) is active today, so the
blast radius is moot. Halting too much is also the safe failure direction. Narrowing it
now would be speculative.

**Trigger to revisit:** the first time 2+ portfolios run simultaneously (e.g. Test 6
alongside Test 5, or a separate crypto sleeve). At that point, decide whether RED should
scope to the portfolio(s) actually causing the drawdown.
