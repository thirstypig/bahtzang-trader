---
id: DOC-018
type: experiment
status: active
phase: G
owner: james
tags: [phase-g, risk, strategies]
links: [PRD-001, DOC-017]
updated: 2026-07-22
---

# Experiment log

Closes the loop on PRD hypotheses. A PRD states a bet; this file records whether the bet
paid off.

The rule that gives this file its value: **an experiment is logged when it starts, with
its result left `pending`.** Writing the entry after you know the answer produces a
record of successes and quietly loses the failures — which are the entries worth keeping.

**Result:** `pending` · `confirmed` · `refuted` · `inconclusive` · `abandoned`

---

## EXP-001 — Does the post-fix system produce zero losing weeks?

| | |
|---|---|
| **Links** | PRD-001, RISK-001 |
| **Started** | 2026-06-16 |
| **Result** | **refuted** |
| **Concluded** | 2026-07-22 |

**Hypothesis.** After the exit-poor design was fixed (real unrealised P&L, a 3:30 PM exit
cycle, the no-repeat constraint removed), a fresh $10,000 paper portfolio — Test 5 —
would trade for 30+ executed trades with **zero losing weeks**, meeting the Phase G gate.

**What happened.** 31 executed trades. The count gate passed; the losing-weeks gate did
not.

| Week | Close | Change | |
|---|---:|---:|---|
| 2026-06-29 | $9,469 | -$531 | loss |
| 2026-07-06 | $9,483 | +$14 | ok |
| 2026-07-13 | $9,289 | -$194 | loss |
| 2026-07-20 (partial) | $9,250 | -$39 | loss |

**Caveats that weaken this result.** Two, and they matter:

1. The first 13 days produced **no trades at all** — a retired model id killed every
   cycle silently (RISK-003). The run is shorter than the calendar suggests.
2. The equity curve was **corrupted for the entire run** by the $0-price bug (RISK-002).
   It reported -40.8% when reality was -7.5%. The weekly figures above come from a
   rebuild against real closes, not from what was recorded at the time.

**What it does tell us.** All five *open* positions were flat-to-green; **100% of the
-$752 loss was realised**, from exits averaging -10% to -24% against a nominal 5% stop.
The failure is exit discipline, not stock selection.

---

## EXP-002 — Do broker-held ATR stops turn expectancy positive?

| | |
|---|---|
| **Links** | RISK-001, RISK-005 |
| **Started** | not yet — designed 2026-07-22 |
| **Result** | **pending** |

**Hypothesis.** Replacing the prompt-suggested stop with a broker-held stop attached at
entry — sized at 2×ATR(14), with a daily trailing ratchet and a 5% portfolio heat cap —
raises expectancy above zero by cutting the tail of large losses without capping winners.

**We are wrong if.** Win rate falls far enough that tighter stops cost more in
stopped-out-then-recovered trades than they save in avoided large losses. Momentum
strategies often have low win rates; a stop that sits inside normal noise makes that
worse, not better.

**How we will measure it.** Expectancy per trade over 30+ executed trades, compared
against the EXP-001 baseline of approximately -$58/trade. Requires honest snapshots,
which now exist.

**Open decision blocking the start:** whether this runs on Test 5 in flight or a fresh
Test 6.

---

<!-- Add new experiments at the TOP, with result: pending, at the moment they start. -->
