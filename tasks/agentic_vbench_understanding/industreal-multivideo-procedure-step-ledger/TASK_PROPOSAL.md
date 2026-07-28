# Task Proposal — IndustReal Multi-Video Assembly-State Checkpoint Ledger

**Family:** `agentic_vbench_understanding`

**Proposed task ID:** `industreal-multivideo-procedure-step-ledger`

## Motivation

An industrial assistant needs to understand the result of a procedure, not merely
recognize that a person is manipulating a part. It should know whether a component
was installed correctly, installed incorrectly, removed, or later corrected, and how
each change affects the complete assembly. This task turns that requirement into a
verifiable long-horizon benchmark: the agent must reconstruct the evolving physical
state from video rather than identify isolated actions.

## One-line

Given seven silent egocentric videos of people assembling or maintaining the same
construction-toy car, reconstruct every stable assembly-state transition: when it
happens, which procedure steps change, and the complete resulting 11-component state.

## The videos and question

The agent receives seven anonymized 1280×720, 10 fps recordings (`A.mp4` through
`G.mp4`) selected from the public
[IndustReal v2 dataset](https://doi.org/10.4121/b008dd74-020d-4ea4-a8ba-7bb60769d224.v2).
They total approximately 24 minutes and contain no audio. A visual reference PDF shows
the toy-car components and canonical assembly states.

For every stable transition, the agent writes one checkpoint to
`/workspace/output/solution.json`:

```json
{
  "checkpoints": [
    {
      "video": "A",
      "time_s": 12.3,
      "changes": [3, 6],
      "state_after": [1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0]
    }
  ]
}
```

The row above is a fictitious format example. `changes` uses a closed 33-step
vocabulary covering correct installation, incorrect installation, and removal.
`state_after` uses `-1`, `0`, and `1` for incorrectly installed, absent, and correctly
installed, in a fixed 11-component order.

A checkpoint is the earliest frame where the physical assembly state has changed,
not the end of the surrounding hand action. Initial states are not events; repeated
removals and reinstallations are included; simultaneous component changes form one
checkpoint. Times use each original video's absolute timeline and must be within
2 seconds of the transition.

## Why it is hard and long-horizon

This is state tracking rather than isolated action recognition. The agent must
distinguish manipulation from a completed physical transition and then propagate that
transition through every later state vector.

- Video B reaches an incorrect bracket-and-screw state, removes both components, and
  later installs them correctly.
- Video C starts with a complete car, removes several rear components, replaces part
  of the chassis, and rebuilds it over more than two minutes.
- Video G removes and reinstalls the rear chassis twice, so neither its initial nor
  final frame reveals the intervening ledger.

One missed removal or simultaneous change can make several later checkpoints wrong.
The answer is not displayed as text and cannot be recovered by OCR, a single frame,
or a final-state comparison.

## Ground truth and scoring

Ground truth comes from the canonical structured procedure-step-recognition records
published with IndustReal v2 for the seven selected validation recordings:

- `PSR_labels_raw.csv`: timestamped 11-component states;
- `PSR_labels_with_errors.csv`: the corresponding published step-completion events,
  including incorrect completions.

The exact label archive is pinned at
`https://data.4tu.nl/file/b008dd74-020d-4ea4-a8ba-7bb60769d224/bb336949-248c-4ae6-82ef-107dbe61d10f`
with SHA256
`20bd1e3089123b5b28ccfe57647f8b0a2822d4a3565830db4ef87d0182ebc248`.

The checked-in deterministic builder treats the first state as an initial condition,
turns every later raw state row into a checkpoint, derives all changed step IDs,
copies the complete post-transition state, and converts the published 10 fps frame
number to seconds. It asserts exact frame-and-step agreement with the independently
published event representation. It also records `incorrect -> absent` state changes
as removals. This produces **47 checkpoints** without task-author timestamps or state
labels. The answer key remains verifier-side and is never present in the agent image.

The pure-Python verifier computes checkpoint F1 using maximum order-preserving
one-to-one matching. A true positive requires the exact video, all changed step IDs,
the complete `state_after` vector, and time within 2 seconds. Oracle is `1.0`; an empty
submission is `0.0`.

The complete state vector is deliberately part of the scored skill rather than a
partial-credit tier. The task is meant to measure persistent physical-state tracking,
not only event localization: after one missed removal or incorrect installation, the
agent must detect and repair its internal state on later checkpoints. The verifier
still reports video-and-time and changed-step matches as diagnostics, but they do not
contribute to reward.

## Agent calibration

The current version was run end to end with Codex, Claude Code, and Antigravity
through Harbor:

| Harness | Model | Reasoning | Reward | Tool-call turns |
|---|---|---|---:|---:|
| Codex 0.144.6 / Harbor 0.6.6 | `openai/gpt-5.6-sol` | high | `0.065934` | `108` |
| Claude Code 2.1.220 / Harbor 0.20.0 | `claude-opus-4-8` | xhigh | `0.000000` | `492` |
| Antigravity 1.1.8 / Harbor 0.20.0 | `gemini-3.5-flash` | high | `0.000000` | `185` |

Codex predicted 44 checkpoints and fully matched 3 of 47. Thirteen predictions matched
video and time, six also matched every changed step ID, and three additionally matched
the full resulting state. Claude predicted 43 checkpoints; ten matched video and
time, three also matched every changed step ID, and none matched the full resulting
state. It systematically treated the short rear chassis as unused and missed the
single incorrect-install state.

Antigravity identified 48 candidate checkpoints but submitted the list at the JSON
root instead of under the required `checkpoints` key, so the verifier rejected its
schema. A read-only diagnostic that supplied only the missing wrapper found 11
video-and-time matches, three changed-step matches, and zero complete-state matches;
the diagnostic F1 therefore also remained `0.0`. All three runs satisfy the current
proposal targets: reward below `0.10` and more than 50 tool-call turns.

## Anti-shortcut

Measured with the same model and reasoning level:

| Condition | Reward |
|---|---:|
| Prompt and schema, no media | `0.000000` |
| One midpoint frame per video | `0.000000` |
| Every native frame pasted as contact sheets, all tools disabled | `0.025000` |

All three are below the required `0.15` ablation ceiling. The frame-dump run had zero
tool calls and matched only 2 of 47 checkpoints, supporting the claim that an agentic
inspection and state-maintenance workflow is necessary.

## Status

The Harbor task, deterministic builder, verifier, oracle, regression tests, all three
required end-to-end trajectories, and measured ablations are implemented. Media and
labels are downloaded from the original 4TU.ResearchData release with pinned SHA256
checks; IndustReal is released under Apache 2.0 and is attributed in `NOTICE.md`.

The Codex, Claude Code, and Antigravity runs clear the initial difficulty and
long-horizon gates. The calibration evidence required by the current community build
guide is complete.
