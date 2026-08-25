---
title: Antigravity App handoff for a Melee full-baseline run
summary: Research, isolate, and execute one review-quality single-agent Antigravity baseline attempt.
read_when: Opening this repository in Antigravity.app to prepare and run the Melee task once.
---

# Objective

Prepare and execute exactly one clean, review-quality **single-agent full
baseline** for the Melee combo-and-kill causal-ledger task. First prove that the
installed Antigravity runtime can authenticate and complete a real tool-capable
model request through the route used by the benchmark. Only after that smoke test
passes may you run the one formal attempt.

Work from this repository as the orchestration layer:

```text
/Users/zsj/Documents/agentic-vbench-melee-pr65
```

The formal task is:

```text
tasks/agentic_vbench_understanding/melee-nouns-bowl-2025-combo-kill-causal-ledger
```

Do not modify the task, Docker environment, prompt, verifier, ground truth, source
video, or existing calibration data. Do not commit, push, open a pull request, or
publish anything. New untracked runtime and evidence files are allowed only under
this handoff's `antigravity/` directory.

# What Makes This a Full Baseline

The formal attempt must use one Antigravity agent, the locked model below, one
agent container/workspace, one attempt, one concurrent trial, and zero retries.
It may use normal local analysis tools, but it must not create subagents, delegate
video inspection, use parallel workers, call another model, or request human hints.

Phase-1 infrastructure research is allowed only in an empty scratch task. It must
not use the Melee video, benchmark prompt, task sources, or benchmark workspace.

# Locked Identities

| item | required value |
|---|---|
| repository commit | `c780b6d8e85db5aaef1b741c8c2ecbc89d377727` |
| task prompt SHA256 | `911e5db8cefdff943ba7e411e1e3ee74253abf132e3e4fa78af57c4c0c863caf` |
| source video SHA256 | `02f18fd7f4796800eece0400b1b1f315a36778b57b9ef4a64d1b30aa3b539749` |
| source video | `/Users/zsj/Documents/agentvbench/materials/source/melee-nouns-bowl-2025/match.mp4` |
| model | `Gemini 3.5 Flash` |
| harness | `Antigravity.app 2.3.1` |
| Harbor | record the installed version; use the same version for smoke test and run |
| agent timeout | `3600` seconds; do not set a timeout multiplier |
| attempts/retries | one attempt; zero retries |

The model and harness version are fixed before the formal run. Do not change either
after observing an output. Do not substitute a direct Gemini API script for
Antigravity.app.

# Isolation Rules

During the formal agent phase, the model may receive only the unchanged checked-in
instruction and `/workspace/materials/match.mp4`. It may write intermediate data
only under `/workspace/work`, and it must write its answer to
`/workspace/output/solution.json`. Verifier files may exist outside the agent
workspace but must never be visible in `/workspace` during agent execution.

Never expose to the formal model ground truth, judge/scorer/test/source code, old
solutions, rewards, scores, trajectories, ablations, reviews, public VOD pages,
replays, online statistics/results, browser/search, WebFetch, MCP, connectors,
external files, or user hints. Do not paste or rewrite the task prompt.

Disable general agent egress. Only unavoidable Antigravity/Google model-provider
traffic may remain; retain evidence of the actual policy. Never print, inspect,
persist, or ask the user to paste OAuth tokens. Use the product's normal credential
handling and report non-secret authentication errors only.

# Phase 1: Infrastructure Research Only

Use an empty temporary directory and a harmless task such as writing and reading a
file containing `OK`. Do not use any Melee material.

1. Record installed Harbor, Docker/Colima, Antigravity.app, and any `agy` CLI
   versions available to the actual execution route.
2. Verify normal Antigravity authentication without reading or printing token data.
3. Run the actual Antigravity adapter with `Gemini 3.5 Flash`, streamed output, and
   at least one normal local tool action.
4. Retain non-secret evidence of model identity, app/CLI version, tool result,
   native trajectory/log location, and exit status.

Proceed only if authentication, a substantive model response, and a normal tool
action all complete without a model-not-found, HTTP 4xx/5xx, transport, streaming,
container, or nonzero-exit failure. A successful login or direct Gemini API call is
insufficient. If this phase fails, stop and report `invalid infrastructure
diagnostic`; do not create a benchmark score or use another harness.

# Phase 2: One Clean Benchmark Attempt

Proceed only after Phase 1 passes.

1. Verify the repository commit, prompt hash, and local video hash above.
2. Inspect the installed Harbor/Antigravity integration and create a new, untracked
   wrapper/configuration only under `calibration/manual-reruns-20260825/antigravity/`.
   It must use Antigravity.app with `Gemini 3.5 Flash`, a UTC-unique job name, raw
   logs, and the source video as the sole material.
3. Before launch, verify exactly one agent, one task, no retry, no concurrency above
   one, no delegated-agent feature, and the checked-in 3600-second timeout.
4. Launch exactly one trial. Do not add project context, prior app sessions, browser
   tools, or any extra files to the benchmark agent.
5. Once the agent exits, invoke the verifier exactly once and preserve the original
   solution, raw/native trajectory, Harbor logs, reward, and verifier details.

If the formal attempt receives zero substantive model tokens, fails before a
meaningful response, or lacks `solution.json` due to startup/OAuth/transport failure,
record `invalid infrastructure diagnostic`, not a zero score. Do not retry it under
this full-baseline attempt.

# Task Output Requirements

The task is to infer qualifying punish conversions chronologically from ten
concatenated Melee games, using only the provided video. The final JSON at
`/workspace/output/solution.json` must contain exactly an `events` array. Each event
has only `game`, `attacker`, `victim_stock_before`, `hit_count`, `damage_band`, and
`terminal`; the original task instruction defines every boundary and allowed value.
Do not add timestamps, move names, explanations, confidence fields, or
non-qualifying events.

# Evidence and Final Report

Do not edit `calibration/scores.md`. Preserve the whole job directory. Scan any
artifact before sharing it for credentials; if one is detected, report only the
affected file path.

Report:

1. Phase-1 result and exact Antigravity/App/CLI, Harbor, and model versions;
2. job/trial paths, task commit, Docker image ID, and locked input hashes;
3. start/end timestamps, final status, and validity decision;
4. reward plus prediction count, schema-valid count, and all available precision,
   recall, F1, exact-match, and partial-match diagnostics;
5. tool-call count, native trajectory/log paths, and their SHA256s;
6. solution, reward, and verifier-detail paths, byte sizes, and SHA256s; and
7. confirmation that this is a one-agent, one-attempt, zero-retry run with no
   external data or model delegation.

End with exactly one classification: `valid single-agent full baseline` or
`invalid infrastructure diagnostic`, followed by the concrete reason.
