---
title: Doom checkpoint state tracking Spec Card
summary: Scope, evidence, and calibration status for the final Doom understanding task.
read_when: Reviewing or calibrating doom-checkpoint-state-tracking.
---

# Doom checkpoint state tracking

Status: final task built; three-agent difficulty calibration, required
anti-shortcut ablations, stable media hosting, and a clean Antigravity terminal
run are complete.

Task: `agentic_vbench_understanding/doom-checkpoint-state-tracking`

Cognitive level: `reasoning`.

## Modalities

- Video: required to identify interactions, entities, ordering, and state changes.
- Audio: not used; the video is silent.

## Question and output

Given one silent 1280x720 gameplay video containing six episodes, reconstruct every
scored interaction and its complete post-event state. The strict JSON schema uses
episode-local integer milliseconds and records event type, entity, active weapon,
held keys, active switches, open doors, and current checkpoint.

## Evidence chain

- Episode 01 at 53.714 s: checkpoint alpha saves the active-switch snapshot.
- Episode 01 at 87.514 s: switch white changes after that snapshot.
- Episode 01 at 106.057 s: restoring checkpoint alpha reverts switch white while
  persistent state remains.
- Episode 01 at 326.429 s: a later restore requires the beta snapshot plus the
  preceding keys, weapons, doors, and switches.

## Ground truth

Tier: `logged`. Media generation follows a seeded scripted plan, but ground truth
is not copied from that plan or parsed from the demo. When an interaction fires,
ACS publishes its sequence, identity, and atomic post-event state through ViZDoom
USER variables. The generator polls them every game tic while recording the demo,
then replays that exact demo and rejects frame-hash mismatches. The final
verifier-side ledger has 138 events across six episodes. Manual annotations: zero.
The generation and observability audit is retained in
`provenance/generation_audit.json`.

## Verification

The deterministic verifier aligns events by episode, type, entity, and timestamp
within 750 ms. Ties minimize timestamp error before using the earlier prediction.
Reward is 90% exact full-state event-F1 and 10% gated per-field F1, macro-averaged
over six episodes. Set fields require exact set equality. Oracle: `1.000000`.
Null: `0.000000`.

## Difficulty

Codex CLI 0.145.0 with `gpt-5.6-sol` at xhigh scored `0.065234` over 279
non-plan tool calls. Antigravity CLI 1.1.8 with `gemini-3.5-flash-high` at high
completed with terminal `SUCCESS` and scored `0.002500` over 30 conservative
non-scheduler tool calls.
Claude Code 2.1.220 with `claude-opus-4-8` at high scored `0.050308` over
315 tool calls in one resumable session. Measurements and raw trajectories are
in `calibration/scores.md`.

## Anti-shortcut

Measured with Codex CLI 0.146.0, `gpt-5.6-sol`, xhigh: no media scored `0.000000`,
one frame scored `0.000000`, and 120 uniformly sampled frames with no video or
sampling tools scored `0.000423`. The task disables HUD, automap, messages, audio,
and event notifications; verifier data and episode seeds are absent from the
agent image. Answers and raw trajectories are in `calibration/ablations/`;
measured rewards are in `calibration/scores.md`.

## Input

- URL: `https://archive.org/download/checkpoint-sequence-recording-01/doom-checkpoint-state-tracking.mp4`.
- SHA256: `257680b3284d97a108b779fab034f5ad8d89ed08db4527bd203a601806b5736c`.
- Length: 43.845714 minutes.
- Resolution: 720p.
