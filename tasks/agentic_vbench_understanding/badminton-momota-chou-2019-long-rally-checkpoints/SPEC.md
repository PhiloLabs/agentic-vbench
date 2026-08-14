---
title: Badminton Long-Rally Checkpoint Reconstruction Spec
summary: Spec Card for the full-match badminton long-rally understanding task.
read_when: Reviewing or calibrating this task.
---

# Task Spec Card

```yaml
task: agentic_vbench_understanding/badminton-momota-chou-2019-long-rally-checkpoints
cognitive_level: understanding

modalities_required:
  video: Rally discovery, stroke indexing, player localization, and shuttle destination all require motion evidence.
  audio: Racket-contact acoustics contribute candidate contacts and contact timing; visual evidence remains required for identities and spatial fields.

question: Find every rally with at least 20 strokes and reconstruct the fifth, midpoint, and final checkpoint states.
output_schema: Rally-grouped JSON with set, start seconds, stroke count, winner, and three timestamped hitter/player/shuttle-zone states.

evidence:
  - t=491.92s, audio+video, first qualifying rally and its checkpoint states
  - t=5249.88s, audio+video, final qualifying rally and its checkpoint states

ground_truth:
  source: ShuttleSet match 1, CoachAI-Projects commit 45517f7d4cb936b03f3eabf939cc7959d39226fe
  tier: human-verified
  verification: Six-annotator ShuttleSet source workflow; 100% per-field source-to-reference agreement across all 26 rallies and 78 checkpoints, with zero discrepancies requiring adjudication; frame-rate audit; and four dataset-to-video alignment checks.

scorer:
  metric: Qualification F1 times parent-metadata mean accuracy, checkpoint-timing F1, and mean individual checkpoint-field F1 on matched rallies.
  oracle_reward: 1.0
  null_reward: 0.0

difficulty:
  strong_agent_reward: 0.088068
  tool_call_turns: 281
  agent_model: GPT-5.6 Sol xhigh through Harbor 0.6.6

anti_shortcut:
  single_frame: 0.0 (GPT-5.6 Sol xhigh, one frame at t=3002.28s plus the court grid, 0 tool calls)
  video_only: 0.070958 (GPT-5.6 Sol xhigh, audio stream removed, 208 tool calls)
  audio_only: 0.018403 (GPT-5.6 Sol xhigh, video stream removed, 60 tool calls)
  no_media: 0.0 (Gemini 3.5 Flash High, 36 tool calls, no search or browser use)
  frame_dump_no_tools: 0.013372 (GPT-5.6 Sol xhigh, all 6176 one-second frames in 52 contact sheets, 0 tool calls)

input:
  url: https://www.youtube.com/watch?v=O669aZhH0LI
  sha256: 63e53e871beaa993ff69c210842ac6fc8e9a3290b7d6021daa5eab7a88cef95c
  length_min: 102.9
  resolution: 720
```
