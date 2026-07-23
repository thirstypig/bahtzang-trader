<!--
  PRD TEMPLATE. Copy this file into docs/product/prds/PRD-###-<slug>.md, then:
    1. Uncomment the frontmatter block below (remove the outer <!-- --> wrapper).
    2. Assign the next PRD-### id. Never reuse a number.
    3. Delete every guidance comment as you fill its section.
  This file itself stays in _templates/ and is excluded from the board.
-->

<!--
---
id: PRD-###
type: prd
status: draft          # draft | active | locked | done | deprecated
phase: null
owner: james
tags: []               # controlled vocabulary only — see README-DOCS.md
links: []              # related ADR-###, PRD-###, RISK-### ids
updated: YYYY-MM-DD
---
-->

# PRD-### — <Feature name>

<!-- For a RETROACTIVE PRD (reconstructing a shipped feature), tag every claim:
       [intended]  a deliberate up-front decision — say why you believe that
       [inferred]  reconstructed from the code — a reasonable read, not a fact
       [unknown]   the code cannot tell us — ask, do not invent
     A PRD full of [unknown] is a success. Those are the questions worth surfacing. -->

## 1. Problem statement
<!-- What is broken, and for whom? Concrete about the "before" state. -->

## 2. Strategic rationale
<!-- Why does this exist? Why worth building? Tie to the core value. -->

## 3. User story
<!-- As a [role], I want ... so that ... -->

## 4. Assumptions
<!-- What had to be TRUE for this to be worth building? Name the implicit bets. -->

## 5. Impact & KPIs
### (a) What the metric SHOULD be
<!-- The bet you would make. What would prove this works? -->
### (b) What we can measure TODAY
<!-- Instrumented at all? If not, write "not instrumented". Never invent numbers. -->

## 6. Technical notes
<!-- How it is actually built. -->

## 7. AI implementation notes
<!-- Model, prompt strategy, cost per call. Cost is [unknown] unless measured. -->

## 8. Testing plan
<!-- What exists today vs what should. Be specific about gaps. -->

## 9. What we'd do differently
<!-- The hindsight section. Be candid — this is where the exercise pays off. -->
