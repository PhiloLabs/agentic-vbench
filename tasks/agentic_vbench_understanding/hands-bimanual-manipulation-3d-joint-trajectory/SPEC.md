---
title: Task Spec Card
summary: Right-hand 3D joint trajectory from three egocentric manipulation clips.
read_when: Reviewing or reproducing this video-understanding task.
---

# Task Spec Card

```yaml
task: agentic_vbench_understanding/hands-bimanual-manipulation-3d-joint-trajectory

# 1. What kind of thinking does this task need?
cognitive_level: reasoning
# The answer is metric 3D structure, not an on-screen readout. The agent must track
# the right hand across an egocentric clip, reason about camera geometry (the
# camera model is given) and hand motion parallax over many frames, and recover each
# joint's position in metres. It is spatial/geometric reasoning, not perception.

# 2. Which modalities are REQUIRED (not just present)?
modalities_required:
  video: The 3D joint positions exist only in the moving imagery; they must be
    triangulated/inferred from how the hand and scene shift across frames under the
    given camera model. No single frame or caption carries metric depth.
  audio: not used

# 3. The exact question and output schema.
question: For each query frame in each of the three clips, give the right hand's 20
  canonical skeleton joints as 3D points in that clip's RGB camera frame, in metres.
output_schema: >
  {"clips": {"clip_01": [{"frame": int, "joints_m": [[x,y,z] x20]}], "clip_02": [...],
  "clip_03": [...]}}. joints_m is 20 rows in the fixed joint order given in the prompt,
  metres, camera frame (+Z forward, +X right, +Y down). Scored per joint with a 3 cm
  soft tolerance.

# 4. Evidence chain: the answer depends on many far-apart moments.
evidence:
  - "36 query frames total (12 per clip), spread across the middle 90% of each ~2 min
     clip, so the answer is distributed over the whole timeline, not one lookup."
  - "Each query needs the hand localised in 3D at that instant. The metric scale is
     observable: hand_model.json ships the wearer's rigid bone lengths, so the pixel
     span of an identified bone plus the pinhole intrinsics fixes depth. Turning that
     into 3 cm joints still takes accurate 2D localisation and articulation reasoning
     under occlusion and motion blur, integrated across the clip."
  - "Two hands are present and often overlap; the agent must consistently isolate the
     right hand throughout, which requires following the interaction over time."

# 5. Ground truth.
ground_truth:
  source: The capture rig's logged hand-tracking (per-frame hand model + wrist pose),
    forward-kinematicked to 20 canonical joints and transformed into each clip's RGB
    camera frame using the logged device trajectory and factory camera extrinsics.
  tier: logged
  verification: "Reprojected joints land on the visible hand in the rectified pinned
    frames (checked after expressing the joints in the rectified camera frame, which the
    earlier revision got wrong by the upright rotation); per-frame
    hand bounding boxes from the rig agree; hand scale (wrist-to-fingertip spans) is
    anatomically consistent (~18-22 cm hand span) across all queries."

# 6. Scorer: deterministic code only.
scorer:
  metric: >
    Per joint, soft hit = clip(1 - ||pred - gt|| / TAU, 0, 1) with TAU = 0.03 m.
    reward = mean soft hit over all (clip, query frame, joint) = 720 scored units.
  oracle_reward: 1.0
  null_reward: 0.0   # measured: empty/None submission

# 7. Difficulty: measured with real strong-agent runs.
difficulty:
  strong_agent_reward: 0.041  # Fable 5 fresh run on the fixed task, shipped configuration
  tool_call_turns: 55       # num_turns of the closing result record
  agent_model: Claude Code CLI (Fable 5)
  # Shipped configuration: run inside the built task image, network restricted to the
  # model endpoint by a DNS allowlist gate (allow_internet=false semantics; the model
  # channel is harness-side in Harbor), 60 minute budget, shipped tools only.
  # History: on the earlier revision (native-frame GT, see calibration/scores.md) every
  # agent scored 0.0; re-scoring the strongest of those runs (a network-open Fable run
  # that installed MediaPipe, rollouts/claude-code-fable-opennet.jsonl) under the fixed
  # frame gives 0.036, still well under the bar.
  # Transcript of the calibration row: rollouts/claude-code-fable.jsonl.

# 8. Anti-shortcut ablations (each must be <= 0.15). Real Claude Code run per row; see
# calibration/ablations/.
anti_shortcut:
  single_frame: 0.009     # one frame per clip + intrinsics; real run on the fixed task
  video_only: n/a          # audio not used
  audio_only: n/a
  no_media: 0.0         # only cameras.json + queries.json
  frame_dump_no_tools: 0.0  # pre-dumped frames, no shell tools

# 9. Input media (three short clips; comparison/multi-clip -> exempt from length floor).
input:
  clips: 3
  # every file is fetched from this base with {base}/{name}, pinned by SHA256 in the
  # Dockerfile. Same host as the v1.0 families.
  base_url: https://huggingface.co/datasets/yalesunxiatao/agentic_vbench_understanding_hands/resolve/main
  sha256:
    clip_01.mp4: 22d4f7e060ee79eb77eadd58b92c0f3a3e840640aba2f3afc6322aee47c8b729
    clip_02.mp4: 5323761ef008f7f0e3d317a9b477c4f9ffd80da6da3504b3280324af93a47544
    clip_03.mp4: 6fc266fd070b00e547642ef3e0613ef82ca13a58b8042a86c4259f7bf8269874
    cameras.json: 753c37861a52a82d0689a571afed6ce5f90dcc358367a54c8a637919fb565d1c
    queries.json: f2dd1a835408b239b979b874c6bc09dee13a8b3bb87a970f1407a1163137bb88
    hand_model.json: 5ff5d0b0fa0dec2b6e52bce887299f6bfa2840cdf549eb6778c2f95cc6e0e50b
  length_min: ~2 min each (short-clip set; exempt from the 10-min single-video floor)
  resolution: 1024x1024 pinhole (>= 720p; rectified from a wider capture)
```
