---
title: Task Spec Card
summary: Object 6DoF pose trajectory from three egocentric manipulation clips.
read_when: Reviewing or reproducing this video-understanding task.
---

# Task Spec Card

```yaml
task: agentic_vbench_understanding/objects-tabletop-manipulation-6dof-pose-trajectory

# 1. What kind of thinking does this task need?
cognitive_level: reasoning
# The answer is a metric 6DoF pose per frame: position and orientation in the camera
# frame. The agent must track the designated object through an egocentric clip,
# reason about the given camera geometry, and infer both where the object is (metric
# depth) and how it is oriented over time. Spatial/geometric reasoning, not a readout.

# 2. Which modalities are required (not just present)?
modalities_required:
  video: The 6DoF pose lives in the moving imagery. Metric depth and 3D orientation
    resolve only by tracking the object's silhouette/features across frames under the
    supplied camera model. No frame or caption states the pose.
  audio: not used

# 3. The exact question and output schema.
question: For each query frame in each of the three clips, give the designated target
  object's 6DoF pose (translation in metres + orientation quaternion) in that clip's
  RGB camera frame.
output_schema: >
  {"clips": {"clip_01": [{"frame": int, "t_xyz_m": [x,y,z], "q_wxyz": [w,x,y,z]}],
  "clip_02": [...], "clip_03": [...]}}. t in metres (camera frame +Z fwd, +X right,
  +Y down); q a unit quaternion, w first. Scored by ADD with tau = 10% of the object
  diameter.

# 4. Evidence chain.
evidence:
  - "36 query frames total (12 per clip) spread across the middle 90% of each ~2 min
     clip: the answer is distributed over the whole timeline."
  - "Each pose needs both metric depth and 3D orientation, which for a monocular view
     resolve only by integrating the object's motion/parallax across many neighbouring
     frames plus the supplied camera intrinsics and object point set."
  - "The agent is given the object's canonical point set (object_points.json), so the
     pose is well defined and the task is solvable; the difficulty is estimating it from
     a single moving view, not guessing an unknown reference frame."
  - "The object is grasped, lifted, and turned over. Its pose changes substantially
     across the clip (camera-frame net displacement ~0.4-1.9 m), so a single guess
     cannot cover the trajectory."

# 5. Ground truth.
ground_truth:
  source: The capture rig's logged object-pose tracking (per-frame T_world_object),
    transformed into each clip's RGB camera frame using the logged device trajectory
    and factory camera extrinsics.
  tier: logged
  verification: "Object points reprojected with the baked pose overlay the visible
    object in the rectified pinned frames (checked per query after expressing the pose
    in the rectified camera frame, which the earlier revision got wrong by the upright
    rotation); at least 98 percent of the projected points fall inside the image at
    every query; camera-frame depth stays in the plausible arm's-reach range
    (0.1-1.5 m); poses are temporally continuous."

# 6. Scorer: deterministic code only.
scorer:
  metric: >
    Per query, ADD = mean over the object's baked mesh points of ||T_pred·p - T_gt·p||;
    frame_score = clip(1 - ADD / TAU, 0, 1), TAU = 0.10 * object_diameter. ADD-S
    (nearest-neighbour) for symmetric objects (none flagged here). reward = mean over
    36 query frames.
  oracle_reward: 1.0
  null_reward: 0.0   # measured: empty/None submission

# 7. Difficulty: measured with real strong-agent runs on the current design (object_points
# shipped). Reachability of the ADD bar is shown by the partial-credit curve in
# calibration/scores.md; a good model-based pose estimate scores well before it is exact.
difficulty:
  strong_agent_reward: 0.002  # Fable 5 fresh run on the fixed task, shipped configuration
  tool_call_turns: 122       # num_turns of the closing result record
  agent_model: Claude Code CLI (Fable 5)
  # Shipped configuration: run inside the built task image, network restricted to the
  # model endpoint by a DNS allowlist gate (allow_internet=false semantics; the model
  # channel is harness-side in Harbor), 60 minute budget, shipped tools only.
  # History: the earlier revision expressed GT poses in the native camera frame while
  # the clips are rectified upright, so correct pose work read as 0.0 by construction
  # (see calibration/scores.md). Re-scoring the strongest earlier run under the fixed
  # frame gives 0.045, still well under the bar.

# 8. Anti-shortcut ablations (each must be <= 0.15). Real Claude Code run per row; see
# calibration/ablations/.
anti_shortcut:
  single_frame: 0.0     # one frame per clip + intrinsics + object_points; real run on the fixed task
  video_only: n/a          # audio not used
  audio_only: n/a
  no_media: 0.0         # only cameras.json + queries.json + object_points.json

# 9. Input media. Three ~2-minute clips are used as a multi-clip set rather than one
# long video: the three clips are compared against three separate objects, which the
# family README allows in place of a single 10-300 minute video, so the per-video length
# floor does not apply here.
input:
  clips: 3
  objects: [birdhouse_toy, vase, potato_masher]   # all asymmetric
  base_url: https://huggingface.co/datasets/yalesunxiatao/agentic_vbench_understanding_objects/resolve/main
  sha256:
    clip_01.mp4: aefb41b216cc2cbacfca639de8175a29f37006c3be730b118928ce20e27d19ee
    clip_02.mp4: b187d5cbaba972ca715f0ffd670b99b1c77ee9ad579d40b3acdff1b564c114ae
    clip_03.mp4: 56c42f94baecf5a78e2b6e32ed5af59719b51badfc6405d3f67d9b26bbc77520
    cameras.json: 753c37861a52a82d0689a571afed6ce5f90dcc358367a54c8a637919fb565d1c
    queries.json: f9f4f7ec0f65d0bbec38a700e2c3492579f2dc9d44c569643f94cb8c23b150ae
    objects.json: cc9906530da3bfd8b6a97a7586cfc541b23a3e8e2cbe4b9f77e2362562c82f19
    object_points.json: da0889b30ec5dee3723533ab85fa819ec2e49988ee99b76c69669b64ccea22eb
  length_min: ~2 min each (short-clip set; exempt from the 10-min single-video floor)
  resolution: 1024x1024 pinhole (>= 720p; rectified from a wider capture)
```
