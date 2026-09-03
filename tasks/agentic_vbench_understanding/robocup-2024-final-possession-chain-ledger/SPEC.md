---
title: RoboCup possession-chain task spec
summary: Evidence, machine ground truth, scoring, media, and measured calibration for the RoboCup task.
read_when: Reviewing or calibrating the RoboCup possession-chain task.
---

# Task Spec Card

```yaml
task: agentic_vbench_understanding/robocup-2024-final-possession-chain-ledger
cognitive_level: understanding

modalities_required:
  video: Individual kicks, team continuity, attack direction, zones, and chain endings require temporal analysis of the moving match footage.
  audio: not used; the selected public representation has no audio stream.

question: Starting after the first goal, reconstruct every maximal same-team live-play possession chain containing at least two distinct kicks.
output_schema: '{"chains": [{"half": 1|2, "team": "white|black", "kick_count": "integer >= 2", "zone_path": ["defensive|middle|attacking", "..."], "terminal": "turnover|stoppage|goal"}]}'

evidence:
  - First half after the opening goal; establishes the first qualifying chains and each team's initial attack direction.
  - Second-half opening after the teams change ends; establishes the reversed attack directions and later chains.
  - Final visible live-play phase at second-half 0:00; establishes that the last chain ends in a stoppage rather than the later post-live log score change.

ground_truth:
  source: Official RoboCup SSL referee and tracked-vision log for the 2024 final.
  tier: machine-truth
  verification: TIGERs kicked_ball events are filtered by official referee live-play segments; the visible 3:0 state at second-half 0:00 is cross-checked against the log; the later post-live 4:0 change is excluded; tracker jitter is merged by time, position, and persistence.

scorer:
  metric: Maximum-credit order-preserving one-to-one alignment followed by weighted event-level F1.
  core_gate: A prediction can earn credit only when half and team align; neither field earns standalone credit.
  full_credit: 1.0 for an exact kick_count, compressed zone_path, and terminal after the core gate.
  partial_credit: At most 0.5; kick_count exact/off-by-one earns 0.25/0.125 and zone_path exact/edit-distance-one earns 0.25/0.125. Terminal earns no partial credit.
  denominator: Every submitted list entry remains in the precision denominator, including schema-invalid entries and duplicates.
  oracle_reward: 1.0
  null_reward: 0.0

difficulty:
  strong_agent_reward: pending a clean final-image calibration pass
  tool_call_turns: pending a clean final-image calibration pass
  required_lineup: GPT-5.6 Sol; Fable 5 or Opus 4.8; Gemini 3.1 Pro or 3.5 Flash
  prior_runs: superseded because they predate the final scorer and were not run through the pinned isolated environment

anti_shortcut:
  single_frame: protocol fixed; clean Codex measurement pending
  video_only: not applicable as a degradation because the full task input is video-only
  audio_only: not applicable because audio is absent
  no_media: protocol fixed; clean Codex measurement pending
  ocr_only: protocol fixed; clean Codex measurement pending
  frame_dump_no_tools: protocol fixed over all 44032 native frames; clean Codex measurement pending

input:
  url: https://www.youtube.com/watch?v=364zEAsOclU
  sha256: 076bcc59fc48443d24a72a87162021470b9e645b41c858c3ffa5b5b25bae36cd
  length_min: 14.6773
  resolution: 720p
  frame_rate: 50 fps
```

## Ground-truth population

The verifier contains 17 chains: seven in the first half and ten in the second;
ten belong to `white` and seven to `black`; twelve end in `turnover` and five in
`stoppage`. No accepted chain has a `goal` terminal under the task's post-first-goal,
video-aligned definition.

## OCR resistance

The overlay exposes the score and clock but not robot-ball launches, live-play
state, same-team continuity, team-relative field zones, or the event that ends a
chain. OCR can help navigate the match but cannot produce the scored ledger without
temporal gameplay analysis.

## Calibration qualification

The scorer, null/spam regressions, native-frame contact evidence, pinned base image,
and exact ablation protocols are complete. The old local outputs are not claimed as
qualification because they predate the final scorer and isolated environment. One
clean final-image pass remains: Codex plus four Codex ablations, followed by Claude
and Gemini end-to-end runs on the unchanged task. Results and whole-file trajectory
digests belong in `calibration/scores.md`.

## Contact observability

Four sequences of consecutive native 720p50 frames cover both halves and show ball
approach, contact occlusion, direction reversal, and free-flight separation. They are
checked in under `calibration/contact-evidence/` with a digest-checking generator.
This evidence directly audits the perception primitive used by every ground-truth
chain; it is reviewer evidence and is not available to the agent.
