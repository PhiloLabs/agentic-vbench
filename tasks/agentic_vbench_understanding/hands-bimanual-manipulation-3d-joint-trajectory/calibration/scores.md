# Calibration: hands-bimanual-manipulation-3d-joint-trajectory

Deterministic soft-PCK scorer (`steps/solve/tests/judge.py`, TAU = 3 cm). A task clears
the bar when every real agent scores below 0.10 and a real attempt takes more than
50 tool-call turns. Oracle must be 1.0 and an empty attempt near 0.

## Task revision: camera-frame fix and visible queries

While reprojecting the baked joints onto the pinned clips (prompted by the query
visibility finding on the sibling 6DoF task), I found the joints were expressed in the
native RGB camera frame while the shipped clips are rectified with an upright 90 degree
rotation. A method that read the correct joints off the video was therefore failing the
3 cm test by construction. Two fixes, both verified by projecting the ground truth onto
the pinned frames:

1. Joints are now expressed in the frame the video and cameras.json actually describe.
2. Query frames are re-picked with a projection test: all 20 joints must land inside the
   image with a margin (the rig visibility mask refers to the much wider pre-rectification
   FOV, which is how a few earlier queries had the hand outside the pinhole view).

Re-scoring the earlier Fable 5 submission against its own frame set with only the frame
fix applied moves it from 0.0 to 0.036: the task went from failing correct answers to
rewarding them, and the strongest attempt so far still sits well under the 0.10 bar.

## Calibration on the fixed task

| run | score | rollout (tool-call turns) |
|---|---|---|
| oracle | 1.0 | - |
| empty / null | 0.0 | - |
| random guess | 0.0 | - |
| Claude Code CLI (Fable 5) | 0.041 | 55 |

The Fable 5 row is a fresh run on the fixed task under the shipped configuration:
executed inside the built task image, network restricted to the model endpoint through
a DNS allowlist gate (its two pip attempts failed exactly as they would with
allow_internet=false; in Harbor the model channel is harness-side), a stated 60 minute
budget, and only the shipped image tools (ffmpeg plus numpy). It finished on its own in
32 minutes: the closing result record reports num_turns 55, containing 316 tool calls
(the agent parallelised heavily, fanning six vision subagents over the 36 query frames
to annotate 2D joints, then recovered metric depth from the hand_model.json bone
lengths). The score of 0.041 against the 0.0 of every pre-fix run shows the metric
reference works; the remaining gap to the 3 cm tolerance is 2D localisation accuracy
under occlusion and motion blur. Transcript: `rollouts/claude-code-fable.jsonl`.

Runs on the earlier revision (native-frame ground truth) are kept for the record; their
transcripts remain in `rollouts/`:

| run | score | turns |
|---|---|---|
| Claude Code CLI (Fable 5, pre-fix, network open) | 0.0 (0.036 re-scored under the fixed frame) | 64 |
| Claude Code CLI (Opus 4.8) | 0.0 | 67 |
| Codex CLI (GPT-5.5) | 0.0 | 13 |
| Antigravity CLI (Gemini 3.5 Flash) | 0.0 | 45 |
| Cursor CLI (Composer) | 0.0 | 57 |

Those zeros mix two causes that could not be separated at the time: genuine difficulty
and the frame mismatch above. The re-scored 0.036 for the strongest of them is the
honest post-fix reading.

## The 3 cm target is reachable (partial-credit curve)

What a method that recovers joints to a given accuracy scores on the fixed task,
obtained by adding gaussian noise of the stated magnitude to the reference joints and
grading:

| per-joint error | reward |
|---|---|
| 5 mm | 0.733 |
| 10 mm | 0.468 |
| 15 mm | 0.260 |
| 20 mm | 0.140 |
| 30 mm | 0.049 |
| 50 mm | 0.011 |

The reward rises smoothly as accuracy improves, so a genuinely good reconstruction is
rewarded well before it is perfect.

## Anti-shortcut ablations (target ≤ 0.15; real runs on the fixed task)

Each row is a real Claude Code (Fable 5) run on the degraded input, in the shipped image
with the same network allowlist as the calibration row, graded by the same judge.
Transcripts and summaries are in `calibration/ablations/`.

| ablation | score | turns |
|---|---|---|
| single_frame (one still frame per clip + intrinsics) | 0.009 | 36 |
| no_media (only cameras.json + queries.json) | 0.0 | 4 |
| frame_dump_no_tools (pre-dumped frames, no shell tools) | 0.0 | 105 |
| video_only / audio_only | n/a (audio not used) | - |

Raw transcripts are in `rollouts/`, one file per agent, so a reviewer can confirm each
score was earned honestly and count the tool-call turns. Honesty notes verifiable in the
transcripts: the agents were given only `materials/` (clips, camera/query JSON, and the
hand_model.json bone lengths), never the ground truth. The bone lengths fix the metric
scale but carry no pose: every joint position still has to be located in the video, and
the single_frame row shows the scale reference alone recovers almost nothing without the
cross-frame evidence.

Oracle end-to-end verified by building the task image (new queries pulled from the
pinned host) and running setup, solve.sh, then judge.py in Docker: reward = 1.0, and the
agent phase holds no ground truth anywhere in the image.

## Full rollout archive

The in-repo transcripts elide base64 frame payloads; complete versions of every
retained trajectory, frames included, are archived immutably (revision-pinned Hugging
Face dataset, so the URLs can never serve different bytes).

Base URL:
`https://huggingface.co/datasets/yalesunxiatao/agentic_vbench_rollouts/resolve/451af73caefefc845532bcc7db1d618b4eb6b88d/hands/`

| file | sha256 |
|---|---|
| claude-code-fable.full.jsonl (calibration row) | dbf1226fb27a2f56ffb8d77c41abb4c91ec48200d4e7c0b1c0bd2be4800a2b56 |
| ablation-single_frame.full.jsonl | fa4ba782415718d4f09face25ea0032c843cbac56609e0d3d7e21133cbb02988 |
| ablation-no_media.full.jsonl | 91c3525af60e951a99f1dc0e4a0f793b21cf9eb3204cb0022f6db7537221b3d9 |
| ablation-frame_dump.full.jsonl | 83e515db90ea20052795129a83a45fae7ea3fcfe84f8548dbd53d10c2fea78ec |
| claude-code-fable-opennet.full.jsonl (pre-fix run) | 245e13793f0f79d190b550ddd3f0f1a2ebcd23b51493667bf555c395264338f4 |
| claude-code.full.jsonl (Opus 4.8, pre-fix) | cb66f9749df4b383d5e69ac98f4fd1528777fbd2c8b0499fafbfd38f42d7abfc |
| codex.full.txt (pre-fix) | c3bb2ffe75c5928173233a8144276d194edd29b2cd6e15fd7ed7e26229a9d5c1 |
| cursor.full.jsonl (pre-fix) | a90ff084feb83a8a6b2259e08b081cd61b7efdbcbd381862b8f389e114d3eace |
| antigravity.full.txt (pre-fix) | a11075fc2cd1e72d604877bed8e547a63c938bc71f27dfe5a0e6bdd22d7a2d8c |

Redaction is mechanical and content-preserving: absolute host paths from the runner
machine become `/workspace`, and capture-hardware and source-collection identifiers
become neutral phrases so the tasks cannot be reverse-searched from the transcripts. No
lines are removed and no payloads are elided in the archive; the in-repo copies are the
same files after base64 frame elision. The substitution process is described in the
archive repo's README, and the exact script is available to maintainers on request (see
the archive-policy note on the sibling reconstruction PR).
