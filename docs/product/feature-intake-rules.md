---
id: DOC-003
type: intake-rules
status: active
phase: null
owner: james
tags: [foundations]
links: [DOC-002, DOC-004, DOC-005]
updated: 2026-07-22
---

# Feature intake rules

The gate a request must pass **before** it earns a PRD.

This exists because the failure mode of a one-person project is not building too little.
It is building sideways: adding a fifth interesting subsystem while the core one still
has a hole in it. The gate is a speed bump, deliberately.

## The five questions

A request must answer all five. An answer of "not sure" is a valid answer — it just
means the request is not ready yet.

**1. What problem, and for whom?**
Stated as the problem, not the solution. "Positions exit too late" is a problem.
"Add a trailing stop" is a solution wearing a problem's clothes.

**2. Which metric does it move, and to what target?**
Name the number and where it is read from. If nothing measures it today, say so — an
uninstrumented feature is a guess with extra steps.

**3. Does it strengthen the core, or is it periphery?**
The core is the thing this project exists to test. If the answer is "it's adjacent but
interesting," the answer to intake is no.

**4. What does it cost — to build and to run?**
Build cost in rough effort. Run cost in real money and real failure modes: API calls,
another external service to go down, another thing to keep in sync.

**5. What are we deferring to fit it?**
Nothing is free. If nothing is being deferred, the plan is not honest yet.

## The rules

- **Nothing enters `launch-spec.md` without a PRD that clears this gate.**
- **The default answer to a new mid-cycle feature is "not yet — log it in `roadmap.md`."**
  Not "no." Logging it means it is captured and can win on merit next cycle.
- A request that fails the gate is not deleted. It goes to the roadmap with a note on
  which question it failed, so the same idea does not get re-argued from scratch.

## Where things go

| Situation | Destination |
|---|---|
| Passes the gate, building it now | PRD in `prds/`, added to `launch-spec.md` |
| Good idea, wrong time | `roadmap.md` with an `RM-###` id |
| Small and immediately actionable | `todos.md` with a `TD-###` id |
| A decision, not a feature | `engineering/decision-log.md`, or an ADR if costly to reverse |
| An idea that failed the gate | `roadmap.md`, annotated with the reason |
