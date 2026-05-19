---
title: Task-suite build plan
summary: Forward-looking plan for a new task-suite iteration — goals, scope, phase breakdown, and per-task corruption recipes. Filled in at the start of each build cycle.
read_when: Designing a new family of repair/edit tasks, expanding the active benchmark, or laying out the phases of a planned rollout.
---

# Task-suite build plan

This file is a **template** for documenting an in-progress build cycle. Each
iteration fills it in fresh at kickoff. The currently-shipped state is
captured in the more permanent docs (`docs/v4/V4_DESIGN.md`,
`docs/v4/V4_RESULTS_SUMMARY.md`).

## Goal

What does this build cycle deliver? One paragraph: the user-facing
deliverable, the scope of tasks, and the rollout/evaluation target.

## Scope

- Which task families are in / out of scope.
- Per-family rough task count.
- Total wall-clock + cost budget.

## Source materials

| # | Task name | Source clip / dataset | Notes |
|---|---|---|---|
| 1 | ... | ... | ... |

## Phases

| Phase | Deliverable | Owner | ETA |
|---|---|---|---|
| 0 | Env + skeleton | — | — |
| 1 | First-family generator + smoke | — | — |
| 2 | Expand to remaining families | — | — |
| 3 | Rollout + comparison | — | — |
| 4 | Final report | — | — |

## Corruption recipes (one-liner each)

| # | Task | Recipe |
|---|---|---|
| 1 | ... | ... |

## Constraints

- Cost ceiling.
- Local vs Modal execution.
- Determinism (seeds, frozen GT).
- What the agent does and doesn't see.

## Iteration policy

For each task:

1. Build generator → confirm task dir is well-formed.
2. Oracle smoke → expect known reward range. Iterate if outside.
3. Agent rollout → record reward, runtime, cost.
4. Move on. Don't dwell.
