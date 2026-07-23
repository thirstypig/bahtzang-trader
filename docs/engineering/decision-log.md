---
id: DOC-009
type: decision-log
status: active
phase: null
owner: james
tags: [foundations]
links: [ADR-001]
updated: 2026-07-22
---

# Decision log (small calls)

A running one-line log for decisions too small to deserve an ADR but too consequential
to forget. Format: **date · decision · why**.

The test: *would reversing this be an afternoon, or a project?* An afternoon goes here.
A project gets an ADR in `adrs/`.

Newest at the top.

| Date | Decision | Why |
|---|---|---|
| 2026-07-22 | Docs `type` vocabulary extended with `guide`, `solution`, `plan`, `brainstorm` | Without them all 31 existing docs were unindexable by the board |
| 2026-07-22 | Added `RM-###` and `TD-###` id prefixes | Roadmap items and to-dos need stable ids to link to each other and to PRDs |
| 2026-07-22 | `docs/product/roadmap.md` is the planning layer; `frontend/src/data/roadmap.ts` stays the published view | Avoids two sources of truth while keeping ids and PRD links the TypeScript has no place for |
| 2026-07-22 | Snapshots price from Alpaca (`get_indicators`) instead of Alpha Vantage | AV returns HTTP 200 with a rate-limit notice, so failures were invisible and became `$0` prices |
| 2026-07-22 | Carry-forward prices bounded at 7 days (`MAX_CARRY_FORWARD_DAYS`) | Unbounded carry-forward would let a genuine multi-day drawdown hide behind a stale price |
| 2026-07-22 | A portfolio that cannot be fully priced gets **no snapshot row** | Writing a partial valuation understates the portfolio and reads as a real loss to the Phase G gate |

<!-- Add new rows at the top. Keep each to one line — if it needs a paragraph, it is
     probably an ADR. Do not backfill this table from memory: entries should be added
     when the decision is made, otherwise the log becomes a reconstruction rather than
     a record. -->
