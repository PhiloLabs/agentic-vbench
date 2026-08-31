# Calibration: object-reconstruction-from-egocentric-manipulation

Deterministic occupancy-IoU × surface-F² scorer (`steps/solve/tests/judge.py`), scored
after a scale-free best-fit similarity alignment. A task clears the bar when every real
agent scores below 0.10 and a real attempt takes more than 50 tool-call turns.
Oracle must be ~1.0 and an empty attempt near 0.

| run | score | rollout (tool-call turns) |
|---|---|---|
| oracle (reference meshes) | 1.0 | - |
| empty / null (no meshes) | 0.0 | - |
| wrong object (keyboard mesh) | ≤ 0.002 | - |
| Claude Code CLI (Fable 5) | 0.041 | 101 |
| Claude Code CLI (Opus 4.8) | 0.018 | 52 |
| Codex CLI (GPT-5.5) | 0.034 | 14 |
| Antigravity CLI (Gemini 3.5 Flash) | 0.001 | 153 |
| Cursor CLI (Composer) | 0.006 | 116 |

The Fable 5 row is a fresh run on the shipped task, executed inside the built task image
itself (the agent saw only the baked materials), with the full stream transcript in
`rollouts/claude-code-fable.jsonl` ending in a result record (num_turns 102, of which
101 are tool calls). It is the strongest attempt so far and still scores 0.041.

Every real agent scored below 0.10. Fable 5 (101 tool calls), Claude Opus (52), Cursor
(116), and Antigravity (153) all ran well past the 50-turn gate, reconstructing three
full meshes each, yet none matched the true surface well enough: the low scores are the
difficulty of the task, not agents giving up early. Antigravity built a full structure-from-motion pipeline (COLMAP
SIFT features, exhaustive matching, incremental mapping, Poisson meshing) and still landed
at 0.001, which shows that even a textbook multi-view reconstruction on these hand-held,
self-occluding, texture-poor objects is far from the surface accuracy the scorer wants.
The volumetric-occupancy term punishes the coarse, concavity-poor shells the agents
produced, exactly as it punishes a convex hull. Codex ran only 14 turns because it chose
to stop on its own, and its partial attempt scored 0.034.

## Anti-shortcut ablations (target ≤ 0.15; best-case degraded submission scored)

| ablation | score |
|---|---|
| single_frame (silhouette slab, extruded 2D bbox) | coffee_pot 0.006, potato_masher 0.007, spatula_red 0.006 |
| no_media (empty output dir) | 0.0 |
| frame_dump_no_tools (convex hull, best tool-less guess, no concavity) | coffee_pot 0.046, potato_masher 0.003, spatula_red 0.006 |
| wrong object (keyboard mesh) | 0.003–0.009 |
| video_only / audio_only | n/a (audio not used) |

The convex-hull and slab shortcuts are exactly what the volumetric-IoU term defeats:
filling a real concavity (hull) or flattening the object (slab) changes the occupied
volume, so both collapse well below the bar while the true shape scores 1.0. The
potato_masher's thin handle and perforated head make it especially hostile to a convex
hull (0.003).

## Solvability: a correct-but-imperfect mesh is well-rewarded

To show the 0.10 bar is reachable and not a cliff, the reference mesh was degraded and
re-scored (same aligner, same grader):

| degraded reference | clip_01 | clip_02 | clip_03 | mean |
|---|---|---|---|---|
| exact | 1.000 | 1.000 | 1.000 | 1.000 |
| decimate to 5% of faces | 1.000 | 1.000 | 1.000 | 1.000 |
| vertex noise 2% of diameter | 0.141 | 0.120 | 0.087 | 0.116 |

A coarse but correct surface still scores 1.0, and even a noticeably noisy surface (2% of
the object diameter, well beyond a good reconstruction) scores 0.116 mean, above the
strongest real agent (0.041, Fable 5). The gap is reconstruction accuracy, not an unreachable
threshold.

Raw transcripts are in `rollouts/`, one file per agent. The in-repo copies elide base64
frame payloads to keep the repo small; complete versions of every retained trajectory,
frames included, are archived immutably (revision-pinned Hugging Face dataset, so the
URLs below can never serve different bytes).

## Full rollout archive

Base URL:
`https://huggingface.co/datasets/yalesunxiatao/agentic_vbench_rollouts/resolve/08f1723fd59249c3cb54e75d46c2229ddf0ae552/recon/`

| file | sha256 |
|---|---|
| claude-code-fable.full.jsonl | 47c49df867302cdfe18a3ce4d31cd5e968a3d6fd0b6f81feac3c2105879a28b2 |
| claude-code.full.jsonl | a47ab890e71e1fafd2cb9a0d4de017ad57dd4cf200e73fb52c086c68f3540bef |
| codex.full.txt | 9d3d168775ccff3f9f26dd3abf18d90617fda49cbc2939a5c56442bf0cb5b4c8 |
| cursor.full.jsonl | 9094520184d8984567ba1e0a493d0e9c7950b90ce8fd76d88f4a843296093cc1 |
| antigravity.full.txt | a03ab756bf44e65c6a3bd0d882aae712239b9985313805b5b3804cb5218c9949 |

Redaction is mechanical and content-preserving: absolute host paths from the runner
machine are replaced with `/workspace`, and capture-hardware / source-collection
identifiers are replaced with neutral phrases so the tasks cannot be reverse-searched
from the transcripts. No lines are removed and no payloads are elided in the archive;
the in-repo copies are the same files after base64 frame elision. The substitution list
is documented in the archive repo's README.

Oracle end-to-end verified by building the task image (agent materials pulled from
Hugging Face, reference meshes copied verifier-side) and running setup, solve.sh, and
judge.py in Docker (reward = 1.0; per-clip 1.0 / 1.0 / 1.0), repeated three times with
identical scores to confirm the seeded sampler is deterministic. During the agent phase
the image holds no reference mesh and no ground_truth.json.
