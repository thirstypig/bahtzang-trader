---
id: DOC-001
type: guide
status: active
phase: null
owner: james
tags: [foundations]
links: []
updated: 2026-07-22
---

# How this doc system works

This folder is the project's internal knowledge base. The admin board at `/docs` reads
these files directly — it does not read filenames, it reads the **frontmatter block** at
the top of each file plus the first `#` heading for the title.

The rule that makes everything else work: **no frontmatter, no index.** A doc without the
block below is invisible to the board.

---

## The frontmatter block

Every authored doc opens with this. Copy it verbatim and edit the values.

```yaml
---
id: PRD-001                 # stable ID — never reused, never renumbered
type: prd                   # what kind of doc this is (see Type values)
status: draft               # draft | active | locked | done | deprecated
phase: null                 # build phase this relates to, or null
owner: james
tags: []                    # ONLY from the controlled vocabulary below
links: []                   # IDs of related docs — this is the traceability
updated: 2026-07-22         # YYYY-MM-DD, bump when you meaningfully edit
---
```

### Field reference

| Field | What it's for | Notes |
|---|---|---|
| `id` | Stable handle for cross-linking | Assign once. If a doc is superseded, mark it `deprecated` — never recycle its ID. |
| `type` | Drives which board section it lands in | One value from the list below. |
| `status` | Powers the "done" filter and badges | Nothing moves to a separate folder when finished — `done` is just a status. |
| `phase` | Ties work to a build phase | e.g. `F`, `G`, or `null`. |
| `owner` | Who answers questions about it | Single-maintainer project, so this is `james` by default. |
| `tags` | Subject-area filtering | Controlled vocabulary only — see below. |
| `links` | Related doc IDs | The most valuable field. A PRD links its ADRs; a to-do links its roadmap item. |
| `updated` | Staleness signal | Generated docs get this stamped automatically. |

---

## ID scheme

One number block per section. Numbers are sequential within a prefix and never reused.

| Prefix | Used for | Lives in |
|---|---|---|
| `PRD-###` | Product requirement docs | `product/prds/` |
| `ADR-###` | Architecture decisions (big, costly to reverse) | `engineering/adrs/` |
| `DOC-###` | Everything else authored | anywhere |
| `RISK-###` | Entries in the risks register | `under-the-hood/risks-register.md` |
| `EXP-###` | Entries in the experiment log | `under-the-hood/experiment-log.md` |
| `RM-###` | Roadmap items (macro) | `product/roadmap.md` |
| `TD-###` | To-dos (micro) | `product/todos.md` |

`RM-###` and `TD-###` are row-level ids inside a table, not whole files. They exist so a
to-do can point at the roadmap item it serves and a roadmap item can point at its PRD.
Without them, small work has no traceable link to the goal it was meant to advance.

---

## Type values

```
prd | launch-spec | intake-rules | glossary | roadmap | todos
adr | tech-spec | api-docs | decision-log | testing | component-lib
changelog | risk | experiment | privacy | runbook
stats | costs | status
guide | solution | plan | brainstorm | inbox
```

The last four were added to cover documentation this repo already has:

- **`guide`** — how-to and explainer docs (`concepts/`, and this file)
- **`solution`** — post-mortems: a problem hit, diagnosed, and fixed (`solutions/`)
- **`plan`** — dated implementation plans (`plans/`)
- **`brainstorm`** — exploratory thinking, not a commitment (`brainstorms/`)

Without these, **all 31** documents already in this repo would have no valid type and
could not be indexed.

---

## Status values

| Status | Meaning |
|---|---|
| `draft` | Being written. Not to be relied on. |
| `active` | Current and trustworthy. |
| `locked` | Deliberately frozen — changing it requires the feature-intake process. |
| `done` | Finished work, kept for the record. |
| `deprecated` | Superseded or wrong. Kept so links don't rot; `links` should point at the replacement. |

---

## Controlled tag vocabulary

**Thirteen tags. No freeform tags.** Search rots when everyone invents their own label —
you end up with `test`, `tests`, `testing`, and `qa` all meaning the same thing and none
of them finding everything.

| Tag | Covers |
|---|---|
| `trading-pipeline` | The decision→execution cycle: executor, Claude prompts, decision modes, order placement, broker integration |
| `risk` | Guardrails, stops, position sizing, circuit breakers, concentration limits, PDT and wash-sale compliance |
| `portfolios` | Virtual sub-accounts: budgets, virtual cash, kill switches, goals |
| `strategies` | Rules strategies, the screener, backtesting, signal generation |
| `market-data` | Price and info feeds: Alpaca, Alpha Vantage, Finnhub, indicators, earnings |
| `phase-g` | The paper→live graduation track and its gates |
| `frontend` | Dashboard, pages, design system, accessibility |
| `backend` | FastAPI, models, routes, scheduler, auth |
| `database` | Postgres/Supabase, schema, migrations, data integrity |
| `deployment` | Railway, CI, builds, releases |
| `testing` | Test suites, fixtures, coverage |
| `forex` | The siloed forex backtester (separate from the trading pipeline by design) |
| `foundations` | Meta-docs about how this project or its docs work |

Deliberate fold-ins, so you know where to file things rather than inventing a tag:

- Auth and JWT work → `backend`
- Broker and order execution → `trading-pipeline`
- PDT and wash-sale rules → `risk`
- Crypto support → `market-data` (data routing) or `trading-pipeline` (execution)

### Adding a tag

Adding one is allowed; adding one *casually* is not. A new tag needs to earn its place:

1. At least three existing docs would carry it.
2. It isn't already covered by a fold-in above.
3. It gets added to this table in the same commit that first uses it.

---

## Comment inbox

Comments are how a note left on the board becomes work that actually gets done. A comment
that is never resolved is worse than no comment — it trains you to ignore the inbox.

### Comment shape

| Field | Values | Notes |
|---|---|---|
| `id` | `C-###` | Stable, never reused |
| `doc` | a doc `id` | Which document the comment is on |
| `kind` | `question` \| `change_request` \| `note` | Drives ordering in the inbox |
| `status` | `open` → `in_review` → `resolved` | One direction only |
| `author` | who raised it | |
| `created` | ISO 8601 timestamp | Used for newest-first ordering |
| `body` | the comment itself | |
| `resolution` | short note | **Required** when status is `resolved` |
| `resolutionLink` | commit SHA or doc id | **Required** when status is `resolved` |

### The three kinds

- **`change_request`** — something must change. Sorts to the **top** of the inbox.
- **`question`** — needs an answer, may or may not cause a change.
- **`note`** — context for later. No action required.

### Status flow

```
open ──▶ in_review ──▶ resolved
                          │
                          └── requires: resolution note + link
```

A comment cannot reach `resolved` without a note and a link. That rule is the whole
point: it forces the answer to be written down where the next person will find it,
rather than living in someone's head or in a chat thread.

Resolved comments disappear from `INBOX.md` on the next sync and show as resolved on
the board. Nothing is deleted — `_comments.json` keeps the full history.

### The ritual

At the **start** of every session: read `docs/INBOX.md`. Act on `change_request` items,
answer `question` items, then write the resolution so each one clears. Regenerate with:

```bash
node scripts/sync-inbox.mjs
```

`INBOX.md` is **generated** — never edit it by hand. Edit the source comments instead.
