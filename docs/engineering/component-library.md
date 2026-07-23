---
id: DOC-011
type: component-lib
status: draft
phase: null
owner: james
tags: [frontend]
links: [DOC-007]
updated: 2026-07-22
---

# Component library

Reusable UI components in `frontend/src/components/`. **34 files, 8 with tests.**

Document the *reusable* ones — components used in more than one place, or whose props
are non-obvious. A one-off chart used by a single page does not need a row here.

## How to fill a row

`Name` · `Props` (the ones a caller must understand) · `States` (loading, empty, error,
interactive) · `Used by` · `Notes`.

## Navigation & shell

| Component | Props | States | Used by | Notes |
|---|---|---|---|---|
| `TopNav` | TODO | TODO | app shell | Mega-menu: Core / Trading / Forex / Admin. Replaced `Sidebar`. Has tests. |
| `ThemeToggle` | TODO | light / dark | TopNav | Persists to localStorage |
| `HashScroll` | TODO | — | anchor pages | Replaced the `useHashScroll` hook |
| `CrossLink` | TODO | TODO | roadmap, changelog | Pill badge, colour-coded by type |

## Data display

| Component | Props | States | Used by | Notes |
|---|---|---|---|---|
| `TradeTable` | TODO | loading / empty | `/trades` | Has tests |
| `Ticker` | `symbol` | hover card | TradeTable | Company profile + Yahoo link. Has tests |
| `AccountHoldings` | TODO | TODO | dashboard | Has tests |
| `PortfolioPositions` | TODO | TODO | portfolio detail | Has tests |
| `PortfolioCard` | TODO | TODO | `/portfolios` | |
| `DecisionCard` | TODO | TODO | TODO | |
| `DecisionModeBadge` | TODO | — | portfolio views | Has tests |
| `BotStatusBanner` | TODO | active / paused | dashboard | |

## Charts

<!-- All Recharts-based, lazy-loaded via dynamic import with ssr:false, and mocked in
     tests because jsdom cannot render SVG. Worth one shared note rather than repeating
     it per row. -->

| Component | Props | States | Used by | Notes |
|---|---|---|---|---|
| `EquityCurveChart` | TODO | TODO | dashboard | |
| `PortfolioEquityCurve` | TODO | TODO | portfolio detail | |
| `DrawdownChart` | TODO | TODO | analytics | |
| `ReturnDistributionChart` | TODO | TODO | analytics | |
| `AllocationChart` | TODO | TODO | dashboard | |
| `PortfolioAllocationChart` | TODO | TODO | portfolio detail | Has tests |
| `ValueChart` | TODO | TODO | TODO | |

## Controls & feedback

| Component | Props | States | Used by | Notes |
|---|---|---|---|---|
| `KillSwitchButton` | TODO | active / deactivate | portfolio views | Has tests |
| `ConfirmModal` | TODO | open / closed | destructive actions | Has tests |
| `PortfolioStrategyForm` | TODO | TODO | portfolio edit | |
| `Spinner` | — | — | everywhere | |
| `Tip` | TODO | — | TODO | |
| `icons` | — | — | TopNav, cards | Icon set, not a component |

## Conventions

- **Never hardcode `zinc-*` / `slate-*` for theme colours.** Use semantic tokens
  (`bg-card`, `text-primary`, `text-muted`, `text-pos`, `text-neg`) or the
  `.bz-glass*` utilities.
- **Do not paint a background between `body` and a `.bz-glass` card** — the body is the
  painted layer the frosted glass reads through.
- Light theme tints white; dark theme tints **navy**. White at low alpha disappears over
  a dark backdrop.
