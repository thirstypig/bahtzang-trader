---
id: DOC-005
type: roadmap
status: active
phase: null
owner: james
tags: [foundations]
links: [DOC-003, DOC-006]
updated: 2026-07-22
---

# Roadmap (macro)

**What this is, in plain English:** the long-horizon list. Big things, phase-sized,
often months out. If it can be done this week it does not belong here — that is
`todos.md` (DOC-006).

Each item gets a stable `RM-###` id and links to the PRD that specifies it. The id is
how a to-do points back at the goal it serves, so small work stays attached to a reason.

> **Relationship to the app's `/roadmap` page.** The live page is rendered from
> `frontend/src/data/roadmap.ts`. That file is the **published, reader-facing view**.
> This document is the **planning layer** — it carries the stable ids and PRD links the
> TypeScript has no place for. Keep them in the same order; when they disagree about
> what shipped, the TypeScript wins, because it is what the site actually displays.

## The "done" convention

Nothing moves to a separate file when it is finished. Completed items stay right here
with `status: done` and are hidden behind a saved filter on the board. Archiving to a
`done/` folder breaks every link that pointed at the item and destroys the record of
how long things actually took.

## Items

<!-- One row per macro item. Phases in this project so far: F (backtesting framework),
     G (paper → live transition). Fill from the phases; free-form is fine where no
     phase applies. Status uses the same vocabulary as frontmatter. -->

| id | Item | Phase | Status | PRD / links | Notes |
|---|---|---|---|---|---|
| RM-001 | TODO | | draft | | |
| RM-002 | TODO | | draft | | |
| RM-003 | TODO | | draft | | |

<!-- Items that failed the intake gate belong here too, annotated with WHICH question
     they failed (see DOC-003). That stops the same idea being re-argued from scratch
     in three months. -->

## Deferred — failed the intake gate

| id | Item | Failed question | Date | Notes |
|---|---|---|---|---|
| TODO | | | | |
