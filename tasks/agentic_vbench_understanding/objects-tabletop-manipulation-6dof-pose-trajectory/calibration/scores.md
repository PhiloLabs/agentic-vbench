# Calibration: objects-tabletop-manipulation-6dof-pose-trajectory

Deterministic soft-ADD scorer (`steps/solve/tests/judge.py`, TAU = 0.1 x object
diameter). A task clears the bar when a strong agent scores below 0.10 while a genuine
attempt is long-horizon, the oracle scores 1.0, and an empty attempt is near 0.

| run | score |
|---|---|
| oracle | 1.0 |
| empty / null | 0.0 |
| random guess | 0.0 |

Oracle verified end to end by building the task image (materials pulled from Hugging
Face) and running setup, solve.sh, then judge.py in Docker: reward 1.0. The agent phase
was checked to contain no ground truth anywhere on the image; the poses ship verifier
side only (tests/ for the grader, a solution/ copy for the oracle).

## Task revision: camera-frame fix and visible queries

The review found five queries whose target never appears in the pinned clips. Chasing
that, I reprojected the baked poses onto the pinned frames and found something bigger:
the poses were expressed in the native RGB camera frame, while the shipped clips are
rectified with an upright 90 degree rotation. A correct pose read off the video was
failing ADD by construction, which is also why every careful run so far scored exactly
0.0. Three fixes, each verified by projecting the object points onto the pinned frames:

1. Poses are now expressed in the frame the video and cameras.json actually describe.
2. Queries are re-picked with a projection test: at least 98 percent of the object's
   points must land inside the image with a margin (the rig visibility mask refers to
   the much wider pre-rectification FOV, which is how the five flagged frames slipped
   through). All 36 queries were regenerated and checked.
3. ADD still scores on exactly the object_points.json set the agent receives.

Re-scoring the earlier Fable 5 submission against its own frame set with only the frame
fix applied moves it from 0.0 to 0.045, with several frames earning 0.23 to 0.52: the
task now rewards correct pose work, and the strongest attempt so far stays well under
the 0.10 bar.

## Agent runs

| run | score | turns |
|---|---|---|
| Claude Code CLI (Fable 5), fixed task, shipped configuration | 0.002 | 122 |

The Fable 5 row is a fresh complete run on the fixed task under the shipped
configuration: executed inside the built task image, network restricted to the model
endpoint through a DNS allowlist gate (pip installs and lookups fail exactly as they
would with allow_internet=false; in Harbor the model channel is harness-side), a stated
60 minute budget, and only the shipped image tools (ffmpeg plus numpy). It finished on
its own well inside the budget; the closing result record reports num_turns 122. Without
a PnP solver or any CV stack it annotated landmarks by eye and fit poses with hand-rolled
geometry, and one frame scored 0.069 while the rest missed the tolerance: 0.002 overall,
against 0.045 for the earlier network-open 98-minute run re-scored under the fixed frame.
The full stream transcript is `rollouts/claude-code-fable.jsonl` and ends with the CLI's
closing result record.

Runs on the earlier revisions are kept for the record; their transcripts remain in
`rollouts/`:

| run | revision | score | turns |
|---|---|---|---|
| Claude Code CLI (Fable 5, network open, 98 min) | object_points shipped, native-frame GT | 0.0 (0.045 re-scored under the fixed frame) | 226 |
| Codex CLI (GPT-5.5) | before object_points | 0.0 | 12 |
| Cursor CLI (Composer) | before object_points | 0.0 | 62 |
| Antigravity CLI (Gemini 3.5 Flash) | before object_points | 0.0 | no solution produced |

The earlier Fable run built metric landmark models from object_points.json, fit poses
with PnP, and verified them by reprojection; under the native-frame ground truth that
careful work still read as 0.0, which the frame fix above explains. The Antigravity run
executed in a filesystem-isolated Docker container that mounts only `materials/`; it
spent its whole budget probing the clips and produced no solution.json. A Claude Code
(Opus 4.8) run on the pre-object_points revision also scored 0.0; its transcript was cut
mid-run without a result record, so it is not listed as a row.

## The task is solvable, and the ADD bar is reachable

An earlier revision defined the pose in the object's canonical frame without giving the
agent that frame; `object_points.json` (the canonical point set the pose maps from)
fixed that, and the camera-frame fix above removed the remaining systematic mismatch.
To show the bar is reachable, here is what a pose
recovered to a given accuracy scores, obtained by perturbing the oracle poses and grading:

| translation error | rotation error | reward |
|---|---|---|
| 5 mm | 2 deg | 0.80 |
| 10 mm | 5 deg | 0.56 |
| 20 mm | 8 deg | 0.22 |
| 30 mm | 12 deg | 0.04 |

Reward rises smoothly as the pose gets closer, so a good model-based pose estimate is
rewarded well before it is perfect. The remaining difficulty is precision: landmark
correspondences good enough that PnP lands the whole point set inside a tenth of the
object diameter, on handheld objects that rotate and get occluded by the hand.

## Anti-shortcut ablations (target <= 0.15; real runs on the fixed task)

Each row is a real Claude Code (Fable 5) run on the degraded input, in the shipped image
with the same network allowlist as the calibration row, graded by the same judge;
transcripts are in `calibration/ablations/`. Turn counts are the `num_turns` field of
the closing result record in each transcript.

| ablation | score | turns |
|---|---|---|
| single_frame (one still frame per clip + intrinsics + object_points) | 0.0 | 77 |
| no_media (only cameras.json, queries.json, object_points.json) | 0.0 | 5 |
| video_only / audio_only | n/a (audio not used) | - |

## Full rollout archive

The in-repo transcripts elide base64 frame payloads; complete versions of every
retained trajectory, frames included, are archived immutably (revision-pinned Hugging
Face dataset, so the URLs can never serve different bytes).

Base URL:
`https://huggingface.co/datasets/yalesunxiatao/agentic_vbench_rollouts/resolve/451af73caefefc845532bcc7db1d618b4eb6b88d/objects/`

| file | sha256 |
|---|---|
| claude-code-fable.full.jsonl (calibration row) | cb2e4d214f091febfb2a0ae3c026fb9fc52477c114ea8c88054dedcd88de311b |
| ablation-single_frame.full.jsonl | eab1f169daad28b18792a6d2f93ddf22a49cd421b5d8fc25ddcfb65c7b25b708 |
| ablation-no_media.full.jsonl | 158cae33e098c607eba9fe623c1c6a6acd00c4f9ce49a0ed8166420e2c504b6d |
| claude-code-fable-opennet.full.jsonl (98 min network-open run) | 30cb15e6e7ae6ecc46fa4e96a72907428a42a235c59fc53c816e80a8c684e5ad |
| codex.full.txt (pre-object_points) | 3184261807f9de1be9afabf1fa8daeac1532c576563958ea437cc1a2d1234479 |
| cursor.full.jsonl (pre-object_points) | 3d1653b25e4a08217a6ffd799d0d5ca4c493af84695d3d364c0ea15bbb93cf5f |
| antigravity.full.txt (pre-object_points) | 397d7a11e9745962b2f0db65e4ac223d0168b888709b1e9b3e366d09676c8ea5 |

The antigravity file is byte-identical to the in-repo copy: that CLI logs plain
narration without image payloads, so there was nothing to elide. Redaction is mechanical
and content-preserving: absolute host paths from the runner machine become `/workspace`,
and capture-hardware and source-collection identifiers become neutral phrases so the
tasks cannot be reverse-searched from the transcripts. No lines are removed and no
payloads are elided in the archive. The substitution process is described in the archive
repo's README, and the exact script is available to maintainers on request (see the
archive-policy note on the sibling reconstruction PR).
