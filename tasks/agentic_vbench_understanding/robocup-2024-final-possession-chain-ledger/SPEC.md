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
  metric: Event-level F1 using exact order-preserving one-to-one matching over half, team, kick_count, compressed zone_path, and terminal.
  oracle_reward: 1.0
  null_reward: 0.0

difficulty:
  strong_agent_reward: 0.0385
  tool_call_turns: 176
  agent_model: Antigravity local run; Codex Desktop gpt-5.6-sol high and Claude local agent claude-sonnet-5 also measured

anti_shortcut:
  single_frame: not measured in the current submission
  video_only: not applicable as a degradation because the full task input is video-only
  audio_only: not applicable because audio is absent
  no_media: not measured in the current submission
  ocr_only: not measured in the current submission
  frame_dump_no_tools: not measured in the current submission

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

Three local agent outputs have been measured below 0.10; see
`calibration/scores.md`. They are reported as the final current calibration. The
runs were outside Harbor and degraded-input ablations were not measured; no stronger
claim is made.
