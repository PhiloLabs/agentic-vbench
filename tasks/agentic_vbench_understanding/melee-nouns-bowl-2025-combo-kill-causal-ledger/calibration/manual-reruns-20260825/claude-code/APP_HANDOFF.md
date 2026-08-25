---
title: Claude Code App handoff for a Melee full-baseline run
summary: Research, isolate, and execute one review-quality single-agent Claude Code baseline attempt.
read_when: Opening this repository in Claude Code App to prepare and run the Melee task once.
---

# Objective

Prepare and execute exactly one clean, review-quality **single-agent full
baseline** for the Melee combo-and-kill causal-ledger task. First establish that
the installed Claude Code runtime and its chosen model route work through the
same adapter that will execute the benchmark. Only after that smoke test passes
may you start the one formal run.

Work from this repository as the orchestration layer:

```text
/Users/zsj/Documents/agentic-vbench-melee-pr65
```

The formal task is:

```text
tasks/agentic_vbench_understanding/melee-nouns-bowl-2025-combo-kill-causal-ledger
```

Do not modify the task, its Docker environment, prompt, verifier, ground truth,
source video, or existing calibration data. Do not commit, push, open a pull
request, or publish anything. You may create only new, untracked runtime and
evidence files under this handoff's `claude-code/` directory.

# What Makes This a Full Baseline

The formal attempt must have one model agent, one model identity, one agent
container/workspace, one attempt, one concurrent trial, and zero retries. The
agent may use its ordinary local tools inside the container, including video
analysis, but it must not delegate work to subagents, parallel agents, external
workers, or another model. Do not use a prior score to ask for another response,
repair an answer, or select a better rollout.

Infrastructure research before the formal attempt is allowed only in an empty
scratch task. It must not use the Melee prompt, video, task files, or benchmark
workspace. It is not part of the scored attempt.

# Locked Identities

| item | required value |
|---|---|
| repository commit | `c780b6d8e85db5aaef1b741c8c2ecbc89d377727` |
| task prompt SHA256 | `911e5db8cefdff943ba7e411e1e3ee74253abf132e3e4fa78af57c4c0c863caf` |
| source video SHA256 | `02f18fd7f4796800eece0400b1b1f315a36778b57b9ef4a64d1b30aa3b539749` |
| source video | `/Users/zsj/Documents/agentvbench/materials/source/melee-nouns-bowl-2025/match.mp4` |
| Harbor | record the installed version; use the same version for smoke test and run |
| agent timeout | `3600` seconds; do not set a timeout multiplier |
| attempts/retries | one attempt; zero retries |

Before the formal run, select the Claude model in the App/CLI and record its exact
model identifier and Claude Code version. These values are locked when the formal
run starts and must not change after observing its output. Do not substitute a
direct API script for Claude Code.

# Isolation Rules

During the formal agent phase, the model may receive only the unmodified checked-in
instruction and `/workspace/materials/match.mp4`. Its writable working area is
`/workspace/work`, and its required answer path is `/workspace/output/solution.json`.
Harbor may retain verifier files for the later verifier phase, but they must never
be mounted or visible in `/workspace` during the agent phase.

Never expose any of the following to the formal model:

- ground truth, judge/scorer, task solution, test code, or source-construction code;
- old solutions, rewards, scores, trajectories, ablation results, or reviewer text;
- public VOD pages, replay files, match statistics, results, set information, or
  external factual hints;
- browser/search, WebSearch, WebFetch, MCP, connectors, external files, or general
  internet access.

The only allowed egress is the selected model-provider endpoint required by Claude
Code. Do not paste or rewrite the benchmark instruction; use the checked-in file
whose hash is locked above. Preserve actual network-policy evidence.

# Phase 1: Infrastructure Research Only

Do this in a new empty temporary directory, with a harmless prompt such as “write
the word OK to a file and read it back.” Do not use this repository's task prompt
or video.

1. Record the installed Harbor, Docker/Colima, and Claude Code versions.
2. Determine the already configured Claude Code model route without printing,
   reading, or persisting any credential. Ask the user to export a missing
   credential in their own shell; never request it in chat or place it in a file.
3. Exercise the actual Claude Code adapter, including streamed model output and at
   least one normal local tool action.
4. Capture the exact non-secret model ID, endpoint host, runtime version, token
   evidence if available, tool result, and exit status.

Proceed only if a real model response and a normal tool action complete with no
authentication, model-not-found, HTTP 4xx/5xx, transport, container, or streaming
error. A successful `curl` is not enough. If this phase fails, stop and report an
`invalid infrastructure diagnostic`; do not create a benchmark score or replace
Claude Code with another harness.

# Phase 2: One Clean Benchmark Attempt

Proceed only after Phase 1 passes.

1. Verify the repository commit, prompt hash, and local video hash above.
2. Inspect the task's Harbor integration and create a new, untracked execution
   wrapper/configuration only under `calibration/manual-reruns-20260825/claude-code/`.
   It must invoke the installed Claude Code Harbor adapter, create a UTC-unique job
   name, retain raw logs, and pass the source-video path as the sole material.
3. Before launch, verify the config has exactly one Claude Code agent, one task,
   no retry setting, no concurrency above one, the checked-in 3600-second timeout,
   and no subagent/multi-agent capability.
4. Launch exactly one trial. Do not attach a project, user context, or extra files
   to the benchmark agent. Do not inspect the verifier until the agent exits.
5. Run the verifier exactly once after the response. Preserve the unmodified raw
   trajectory, solution artifact, verifier details, reward artifacts, and job logs.

If the formal run receives zero substantive model tokens, fails before a meaningful
response, or cannot produce `solution.json` due to startup/auth/transport failure,
record it as `invalid infrastructure diagnostic`, not as a score. Do not retry it
under this full-baseline attempt.

# Task Output Requirements

The task itself reconstructs qualifying punish conversions across ten concatenated
Melee games. The model must derive the answer only from the supplied video. Its final
file must be valid JSON at `/workspace/output/solution.json` with exactly one
`events` array. Each event must contain only `game`, `attacker`,
`victim_stock_before`, `hit_count`, `damage_band`, and `terminal`; the formal prompt
defines their meanings and all valid values. No explanatory fields, timestamps, move
names, confidence values, or non-qualifying conversions are permitted.

# Evidence and Final Report

Do not edit `calibration/scores.md`. Preserve the complete job directory. Before
sharing logs, scan artifacts for credentials and report only affected file paths if
anything is found.

Report:

1. Phase-1 result, exact Claude Code version, exact model ID, and endpoint host;
2. job/trial paths, task commit, Docker image ID, and locked input hashes;
3. start/end timestamps, final status, and why it is valid or invalid;
4. reward plus prediction count, schema-valid count, and any available precision,
   recall, F1, exact-match, and partial-match diagnostics;
5. tool-call count and the raw trajectory/log paths;
6. paths, byte sizes, and SHA256s for the solution, reward, reward details, and
   raw trajectory; and
7. a confirmation that this was one single-agent, one-attempt, zero-retry run with
   no external data or model delegation.

End with exactly one classification: `valid single-agent full baseline` or
`invalid infrastructure diagnostic`, followed by the concrete reason.
