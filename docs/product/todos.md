---
id: DOC-006
type: todos
status: active
phase: null
owner: james
tags: [foundations]
links: [DOC-005]
updated: 2026-07-22
---

# To-dos (micro)

**What this is, in plain English:** the short list. Small, immediately actionable, and
attached to something bigger. If you cannot say which roadmap item a to-do serves, that
is a signal the work may be drift rather than progress.

Each gets a stable `TD-###` id and links to the roadmap item (`RM-###`) and PRD it
serves.

> There is a separate admin to-do tool at `/todos` backed by `backend/data/todo-tasks.json`.
> That one is a scratch queue for operational tasks. This file is the durable list that
> ties work to goals. If a task matters in a month, it belongs here.

## The "done" convention

Same as the roadmap: nothing moves, nothing gets archived. Finished to-dos stay in the
table with `status: done` and drop out of the default view via a saved filter. The
record of what was done and when is worth more than a short list.

## Open

| id | To-do | Serves | Status | Notes |
|---|---|---|---|---|
| TD-001 | TODO | RM-### | draft | |
| TD-002 | TODO | RM-### | draft | |
| TD-003 | TODO | RM-### | draft | |

## Done

<!-- Kept deliberately. This is the record of velocity — how long things actually took
     versus how long they were expected to take. -->

| id | To-do | Serves | Completed | Notes |
|---|---|---|---|---|
| TODO | | | | |
