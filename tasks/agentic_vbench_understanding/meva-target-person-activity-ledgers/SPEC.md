---
title: MEVA target-person activity ledger task spec
summary: Verifiable claims for the MEVA roster-grounded surveillance activity task.
read_when: Reviewing the task media, ground truth, scorer, or calibration evidence.
---

# Task Spec Card

```yaml
task: agentic_vbench_understanding/meva-target-person-activity-ledgers

cognitive_level: perception

modalities_required:
  video: Target identity, activity type, temporal extent, and target-event association are visible only in the surveillance footage.
  audio: not used

question: Reconstruct every allowed activity occurrence performed by each of ten video-local roster targets in a ten-minute surveillance montage.

output_schema: >
  {"ledgers":[{"reference_id":"reference_NNN","events":[
  {"activity_type":"<closed vocabulary>","start_time_s":number,
  "end_time_s":number}]}]}; timestamps are montage-relative seconds and event
  midpoint error may not exceed 3.0 seconds for temporal credit.

evidence:
  - "t=1.9-11.6s: an early object-handling target performs nested pick-up, carry, and put-down activities."
  - "t=309.6-316.1s: a vehicle target opens a door, enters, and closes it."
  - "t=531.4-534.0s: a late object-handling target performs the final scored activity bundle."

ground_truth:
  source: >
    Official MEVA activity, type, and person-geometry annotations. Activity-local
    person tracks are joined only when they share at least 20 frames with median
    same-frame IoU >= 0.90 and q10 IoU >= 0.80. Components touching configured
    near-miss links are excluded.
  tier: machine-truth
  verification: >
    The builder verifies every configured target is one accepted geometry
    component, includes every closed-vocabulary activity attached to that
    component, rejects interleave-boundary crossings, emits boxed occurrence
    sheets, and records the private actor/activity provenance in a durable audit.
    Independent full-video visual review found and removed one duplicate
    continuous-person pair; the repaired package was re-audited with all 29
    retained events aligned and no remaining identity collision or missed
    qualifying occurrence.

scorer:
  metric: >
    Deterministic identity-aware soft event F1. Matching requires exact roster
    target and activity type. Temporal credit combines midpoint accuracy,
    interval IoU, and duration agreement under monotonic one-to-one assignment.
    Reward is micro soft F1 multiplied by macro target soft F1.
  oracle_reward: 1.0
  null_reward: 0.0

difficulty:
  strong_agent_reward: 0.009443
  strong_agent_reward_range: "0.003459-0.009443 across accepted Codex, Claude, and Antigravity runs"
  tool_call_turns: 80
  agent_model: "Codex CLI 0.147.0 with GPT-5.6 Sol; VS Code Claude Agent SDK with Claude Opus 4.8; Antigravity CLI 1.1.12 with Gemini 3.6 Flash High."

anti_shortcut:
  single_frame: 0.0
  video_only: not applicable; audio is not used
  audio_only: not applicable; audio is not used
  no_media: 0.0
  frame_dump_no_tools: 0.001106

input:
  url: https://huggingface.co/datasets/Jordan8717/agentic-vbench-meva-activity-ledgers/resolve/c3c7b0dc1d8cba7834564350b90d0c96b4178d46/meva_activity_montage.mp4
  sha256: 2d51338a954cb726037116b9b9715ef8dccb7c242753a0e709a03c266fbce344
  length_min: 10.0
  resolution: 1080
```

Input credit: MEVA by Kitware Inc. and IARPA, CC BY 4.0. The montage is a
contributor-created adaptation; see `ATTRIBUTION.md`.

## Prompt-writing checks

- One task: reconstruct all allowed target-person activity occurrences.
- Every scored activity and the complete closed vocabulary are defined.
- The exact output path, JSON shape, time units, and temporal tolerance are
  stated.
- The instruction does not expose annotation provenance or score weights.
- The agent is forbidden from online lookup and cross-camera identity claims.
- This is intentionally classified as hard perception: the difficulty comes
  from exhaustive ten-minute search, fine-grained activity localization, and
  roster-grounded target association rather than cross-event reasoning.
