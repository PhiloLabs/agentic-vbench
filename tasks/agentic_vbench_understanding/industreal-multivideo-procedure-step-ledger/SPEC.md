---
title: IndustReal Multi-Video Assembly-State Checkpoints
summary: Reconstruct 47 complete assembly-state checkpoints across seven anonymized egocentric recordings.
read_when: Reviewing the task's evidence chain, ground truth, scorer, media, or calibration.
---

```yaml
task: agentic_vbench_understanding/industreal-multivideo-procedure-step-ledger
cognitive_level: understanding
modalities_required:
  video: Stable component states, correct versus incorrect placement, and completion times are visible only in the egocentric videos.
  audio: not used; the source RGB recordings are silent
question: Reconstruct every stable state transition, its changed procedure steps, and the complete resulting 11-component state.
output_schema: '{"checkpoints": [{"video": "A".."G", "time_s": number, "changes": [integer 0..32], "state_after": [11 values in -1,0,1]}]}; timestamps use each video timeline and have 2 s tolerance'
evidence:
  - Video B begins with only the base present, reaches an incorrect bracket-and-screw state at 148.8 s, removes both components at 159.7 s, and later installs them correctly at 187.4 s.
  - Video C begins with a complete car, removes the rear wheel assembly at 5.6 s, changes rear-chassis components over the next 97 s, and restores the wheel assembly at 134.9 s.
  - Video G removes and reinstalls the rear chassis twice between 41.6 s and 112.3 s, so the final checkpoint cannot be inferred from the initial or final frame alone.
ground_truth:
  source: Canonical IndustReal v2 PSR_labels_raw.csv and PSR_labels_with_errors.csv records for the seven val_p1 recordings, 4TU.ResearchData DOI 10.4121/b008dd74-020d-4ea4-a8ba-7bb60769d224.v2
  tier: machine-truth
  verification: The checked-in builder derives all 47 checkpoints from the official timestamped state records and asserts exact frame-and-step agreement with the independently published PSR event representation; no task-author timestamps or state labels are introduced.
scorer:
  metric: Checkpoint F1 using maximum order-preserving one-to-one matching; a match requires exact video, all changed step IDs, the full post-transition state vector, and completion time within 2 seconds.
  oracle_reward: 1.0
  null_reward: 0.0
difficulty:
  strong_agent_reward: 0.065934
  tool_call_turns: 108
  agent_model: openai/gpt-5.6-sol with high reasoning, Harbor 0.6.6
  submission_gate: passes the repository strong-agent target of less than 0.10
anti_shortcut:
  single_frame: 0.0 (Codex high; one temporal-midpoint frame retained per A--G video)
  video_only: not applicable; the task is video-only
  audio_only: not applicable; source recordings are silent
  no_media: 0.0 (Codex high; prompt and schema with zero-byte media placeholders)
  frame_dump_no_tools: 0.025 (Codex high; every native 10 fps frame pasted into chronological contact sheets; zero model tool calls)
input:
  url: https://data.4tu.nl/file/b008dd74-020d-4ea4-a8ba-7bb60769d224/cf21602e-4424-42a4-b05d-9897957082ad
  sha256: 556357b3ae5804541d6cef75df724af43170f63df6d3cdfda7150fd175822268
  length_min: 24.0 total across seven recordings
  resolution: 720
  reference_url: https://data.4tu.nl/file/b008dd74-020d-4ea4-a8ba-7bb60769d224/4b6641cf-0034-4875-8ebb-73e35e4a5b91
  reference_sha256: 59628d56cc75de40a8e408eada2e83e7006ece5e42e54bd0dc24bb3a452fe9af
license: Apache-2.0
```
