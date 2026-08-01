---
title: Medvedev-De Minaur Break-Point Ledger Spec Card
summary: Evidence and calibration record for the US Open break-point task.
read_when: Reviewing or calibrating this task.
---

# Task Spec Card

## Submission status

The implementation, oracle, deterministic scorer, and supplied model trajectories are
complete. The independent human annotation and anti-shortcut measurements required
for final acceptance have not been supplied, so this card deliberately records them
as pending rather than claiming that this task is ready to merge. The 720p input is
now pinned to a public release asset; `calibration/media-probe.md` records its
provenance and checksum transition.

```yaml
task: agentic_vbench_understanding/medvedev-de-minaur-2023-us-open-break-point-ledger
cognitive_level: understanding

modalities_required:
  video: The persistent scoreboard, serve attempts, and point outcomes identify each break-point event.
  audio: not used

question: Reconstruct every break-point opportunity and the serve, rally length, and terminal stroke of that point in the full match.
output_schema: JSON events with set, player-specific game and point scores, server, opportunity number, first-serve status, saved/converted outcome, serve direction, rally-shot count, terminal player, stroke type, court position, terminal result, and error type.

evidence:
  - first set, video, De Minaur's break-point opportunities in Medvedev service games
  - second set, video, five break points in De Minaur's 2-1 service game
  - fourth set, video, late break-point sequence in Medvedev's 4-1 service game

ground_truth:
  source: Official US Open match feed for match 1403, cross-checked against the Match Charting Project point log
  tier: human-verified
  verification: The official feed reports Medvedev 5/10 and De Minaur 2/6 on break points, for 16 opportunities total. Scores and outcomes are cross-checked against the corrected MCP point log. Added terminal-shot fields are deterministically decoded from MCP's documented shot notation. A second independent, full-video annotation of all 16 points is still required before this tier can be claimed.

scorer:
  metric: Exact event F1 over all reported fields; each reference event can match at most one prediction.
  oracle_reward: 1.0
  null_reward: 0.0

difficulty:
  strong_agent_reward: 0.0
  tool_call_turns: 87
  agent_model: Codex CLI 0.144.4 with GPT-5.6 Sol, high reasoning, fast service tier

anti_shortcut:
  single_frame: pending
  video_only: not applicable; audio is not required
  audio_only: not applicable; audio is not required
  no_media: pending
  frame_dump_no_tools: pending

input:
  url: https://github.com/inFaaa/agentic-vbench/releases/download/medvedev-de-minaur-2023-us-open-r4-media-v1/medvedev-de-minaur-2023-us-open-r4-720p.mp4
  sha256: d78c9246d5dd36b812c71b5f39bfa43ab86d1a7adf711fb7bbc6ff1d66d618b2
  bytes: 804641210
  length_min: 119.2
  resolution: 720
  status: Pinned public release asset; Dockerfile downloads this exact URL and verifies the checksum at build time.
```

# Ground-truth provenance

The official US Open feed for match `1403` reports break-point conversions of `5/10`
for Daniil Medvedev and `2/6` for Alex De Minaur. The 16-opportunity count is fixed
before shot-level annotation. `calibration/ground-truth-provenance.md` records the
MCP point ids, raw rally codes, and the deterministic decoding used for the oracle.

The Match Charting Project is attributed in the provenance because its data is licensed
CC BY-NC-SA 4.0. The task requires a final independent video pass before review, both
to validate its crowd-sourced shot labels and to establish the stated human-verified
tier.
