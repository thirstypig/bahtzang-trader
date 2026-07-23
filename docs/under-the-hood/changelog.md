---
id: DOC-016
type: changelog
status: active
phase: null
owner: james
tags: [foundations]
links: [DOC-005]
updated: 2026-07-22
---

# Changelog

**What shipped, when — at phase granularity.**

> **Per-release detail lives in `frontend/src/data/changelog.ts`**, which renders the
> `/changelog` page and is type-checked by the build. That file is the fine-grained,
> reader-facing record and stays the source of truth for individual releases.
>
> This document is deliberately coarser: it records **phase completions** — the moments
> where a body of work closed and something changed about what the system can do. If you
> find yourself copying release notes here, stop; you have created a second source of
> truth that will drift.
>
> A future improvement: generate this file from `changelog.ts` in `docs:refresh` so even
> the phase log has a single input. Not built — noted so the option is not forgotten.

## How to add an entry

Append at the top when a **phase** closes, not when a PR merges. Each entry answers:
what changed about the system's capability, and what did we learn?

## Phases

<!-- Fill from the phase history. Known phase labels in this project so far: F
     (backtesting framework) and G (paper → live transition). Earlier phases exist in
     the git history and the /changelog page but have not been reconstructed here —
     the archaeology pass is the right tool for that, not memory. -->

### Phase G — paper → live transition (in progress)

- **Status:** in progress. Gate not met.
- TODO — summarise when the phase closes.

### Phase F — backtesting framework

- TODO — reconstruct from git history and `changelog.ts`.

### Earlier phases

- TODO — reconstruct. Do not write these from memory; read the history.
