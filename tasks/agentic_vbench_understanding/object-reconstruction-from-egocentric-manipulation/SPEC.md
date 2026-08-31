---
title: Task Spec Card
summary: 3D reconstruction of interacted objects from three egocentric clips.
read_when: Reviewing or reproducing this video-understanding task.
---

# Task Spec Card

```yaml
task: agentic_vbench_understanding/object-reconstruction-from-egocentric-manipulation

# 1. What kind of thinking does this task need?
cognitive_level: reasoning
# The output is a full 3D surface mesh, synthesised from many partial views of an
# object being turned over in hand. The agent must integrate silhouettes/appearance
# across the clip under the given camera model into one consistent 3D shape: multi-
# view geometric reasoning, not perception of any single frame.

# 2. Which modalities are REQUIRED (not just present)?
modalities_required:
  video: The 3D shape only emerges from many viewpoints across the clip as the object
    is rotated; no single frame shows the whole surface, and no caption encodes geometry.
  audio: not used

# 3. The exact question and output schema.
question: For each of the three clips, reconstruct the 3D surface mesh of that clip's
  designated target object from how it appears across the clip.
output_schema: >
  One triangle mesh per clip in /workspace/output/, named by clip id: clip_01.obj (or
  .ply/.glb/.stl), clip_02.*, clip_03.*. Each is vertices + triangular faces. Scale and
  pose are free, scored after a best-fit similarity alignment.

# 4. Evidence chain.
evidence:
  - "Each object is grasped, lifted, and rotated through the clip; recovering the full
     surface requires fusing views from far-apart moments across the whole ~2 min clip."
  - "Three separate objects across three clips: the agent must reconstruct each from
     its own clip; there is no shortcut that covers all three."
  - "Self-occlusion means no single frame is sufficient; back and bottom faces only
     appear at specific later moments as the hand reorients the object."

# 5. Ground truth.
ground_truth:
  source: The scanned 3D reference mesh of each interacted object (the capture set's
    object models), sampled to a dense reference point cloud baked into the verifier.
  tier: logged
  verification: "Reference mesh reprojects onto the object silhouette in sampled frames;
    mesh diameters are physically sensible (23-37 cm); each target object is confirmed
    grasped and rotated through the clip (measured object-pose rotation across the clip:
    coffee_pot 145 deg, potato_masher 136 deg, spatula_red > 90 deg), so many distinct
    viewpoints are actually shown."

# 6. Scorer: deterministic code only.
scorer:
  metric: >
    Per clip, after a best-fit similarity alignment (PCA-frame + 24 octahedral rotations
    + similarity-ICP, symmetric trimmed-chamfer ranking): score = (surface-F /
    oracle_f)^2 * (voxel-IoU / oracle_iou), each ratio clipped to 1. The surface F-score
    (self-calibrating tolerance = 2.5 median NN spacings of the reference samples,
    TAU_SPACING_MULT in judge.py) catches wrong/partial surfaces; the flood-filled
    volumetric IoU collapses concavity-filling convex hulls and silhouette slabs. Both
    terms are normalised by their per-object oracle ceilings (the F and IoU the true
    mesh itself reaches under independent resampling+voxelisation, baked at authoring)
    so the true shape scores 1.0. reward = mean over the three clips.
  oracle_reward: 1.0   # measured: 1.0 end-to-end in Docker (per-clip 1.0/1.0/1.0)
  null_reward: 0.0     # measured: empty output dir

# 7. Difficulty: measured with real strong-agent runs.
difficulty:
  strong_agent_reward: 0.041  # Fable 5 0.041, Codex 0.034, Claude Opus 0.018, Cursor 0.006, Antigravity 0.001 (all < 0.10)
  tool_call_turns: 101         # Fable 5 101, Antigravity 153, Cursor 116, Claude Opus 52 (all > 50); Codex 14
  agent_model: Claude Code CLI (Fable 5), Claude Code CLI (Opus 4.8), Codex CLI (GPT-5.5), Antigravity CLI (Gemini 3.5 Flash), Cursor CLI (Composer)
  # Turn gate: four of the five runs (Fable 101, Antigravity 153, Cursor 116, Claude Opus
  # 52) cleared 50 turns and still scored under 0.10, so the low scores are the task being
  # hard, not agents quitting early. Codex (14) stopped on its own. Antigravity ran a full
  # COLMAP structure-from-motion + Poisson-meshing pipeline in an isolated container and
  # still scored 0.001. The Fable 5 run is a current-model run executed inside the built
  # task image itself, so the environment matches the shipped task exactly.
  # Solvability: a correct-but-imperfect reconstruction is well-rewarded. Decimating the
  # true mesh to 5% of its faces still scores 1.0 (a coarse yet correct surface passes);
  # perturbing every vertex by 2% of the diameter still scores 0.116 mean, above the best
  # real agent (0.041, Fable 5). The bar is reachable, agents just do not get the shape accurate
  # enough yet.

# 8. Anti-shortcut ablations (each must be <= 0.15). Best-case degraded submission scored.
anti_shortcut:
  single_frame: 0.007      # silhouette slab (extruded 2D bbox): coffee_pot 0.006, potato_masher 0.007, spatula_red 0.006
  video_only: n/a          # audio not used
  audio_only: n/a
  no_media: 0.0           # empty output / stock mesh; wrong object (keyboard) = 0.003-0.009
  frame_dump_no_tools: 0.046  # convex hull (best tool-less guess, no concavity):
    # coffee_pot 0.046, potato_masher 0.003, spatula_red 0.006

# 9. Input media (three short clips; multi-clip -> exempt from length floor).
input:
  clips: 3
  objects: [coffee_pot, potato_masher, spatula_red]   # three distinct non-convex shapes that need many views (survive the hull test)
  url: https://huggingface.co/datasets/yalesunxiatao/agentic_vbench_understanding_recon/resolve/ab18893ae61a4050aa80c383bf18ee6e9be326da
    # baked at build; every file SHA256-checked (see Dockerfile ARGs). Only the agent-facing
    # materials are hosted here; the reference meshes (answer key) are not, they ship
    # verifier-side under steps/solve/tests/ (grader) and steps/solve/solution/ (oracle).
  sha256:
    clip_01: 2f153d49b5c6b61e58d6b648af1002718dddd2fe2b32c6ba28d4e9d80d388a1c
    clip_02: 56c42f94baecf5a78e2b6e32ed5af59719b51badfc6405d3f67d9b26bbc77520
    clip_03: 9d2cd0f8127622bc5805f4cbaf83efcbf17a9ad8d1f46748a26a9ccb7c5ab546
    cameras.json: 753c37861a52a82d0689a571afed6ce5f90dcc358367a54c8a637919fb565d1c
    objects.json: 08ceed454127f4d8f2186d92a97bfab7f3c183c58e348808ff863a020a857798
  length_min: ~2 min each (short-clip set; exempt from the 10-min single-video floor)
  resolution: 1024x1024 pinhole (>= 720p; rectified from a wider capture)
```
