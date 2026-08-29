# Calibration — usc-wsu-2023-volleyball-block-timeline

Block-only timeline, 23 block points. Deterministic F1 scorer
(`steps/solve/tests/judge.py`). A task clears the bar when every real agent scores
below the ~0.10 line and a real attempt takes more than 50 tool-call turns. Oracle
must be 1.0 and an empty attempt near 0.

## Invariants, from the built image

Built clean (`docker build --no-cache`) from `environment/Dockerfile`, which pulls
the media at a pinned dataset revision and verifies its SHA256 during the build:

| run | reward |
|---|---|
| oracle (`steps/solve/solution/solve.sh`) | **1.0** |
| null (`{"events": []}`) | **0.0** |
| 23-block guess, right anchors and wrong names | 0.0 |

Media inside the image hashes to `13ccbabb…d08ba9e`, matching the pin.
`steps/solve/tests/test_judge.py` covers the scorer's tiers and re-grades every answer
committed under `rollouts/` and `ablations/`, so the numbers below are a test failure
if they ever drift from the scorer.

## Model matrix

Every run below used a workspace containing only the video and the instruction, with
no prior artifact of this task reachable; `run-metadata.txt` beside each rollout
records CLI version, model, effort, instruction hash, media hash and judge commit.

| agent | model / setting | score | work | integrity |
|---|---|---|---|---|
| Codex CLI | gpt-5.6-sol, xhigh | **0.0185** | 158 tool-call items, 31 events | key 0, web 0 |
| Claude Code | Opus 5, xhigh | **0.0** | 270 tool-call turns, 1 event | key 0, web 0 |
| Antigravity | — | not run | — | — |

Two strong agents, both far under the bar, neither getting a single block point fully
correct. Both ended normally rather than being cut off, and both wrote their own
`solution.json`. Codex submitted 31 events and got no block fully correct (one
partial). Opus submitted a single event, and said so plainly: it rebuilt the entire
200-rally timeline from the score bug — reconciling exactly with the final box score,
including two overturned challenges — then reported that it could confirm only one
block point, and that even there the blocker credit was "an inference, not a reading".

That is the intended shape of this task. The timeline layer is tractable; the
attribution layer is not, unless the agent finds the one place it is visible.

Both integrity columns are from the raw transcripts: no reference to a judge, a
ground-truth file or a search. The Codex run is worth one note — three of its 158 tool
calls are attempts to leave the workspace: it listed the host's applications, then
asked for QuickTime Player ("Computer Use was not approved") and for a browser
runtime ("No browser is available"). Both were refused, the only URL string anywhere
in its transcript is `https://example.com/`, and no external content reached it.

A Fable 5 run is archived unscored — it reached 210 tool-call turns of genuine frame
work before that model's credit pool ran out, so it never submitted an answer.
`fable-run.solution.json` is the partial event list recoverable from its transcript at
that point, kept as evidence of where it had got to, not as a submission. Finishing an
interrupted run with a different model was tested and rejected; see
`rollouts/hybrid-fable-then-opus.md`.

## Ablations

Run on the same instruction. A model that declines to answer measures nothing, so
each ablation also demands a best-effort answer; the counts below are what the model
actually submitted.

| ablation | inputs | tools | events submitted | score |
|---|---|---|---|---|
| no_media | instruction only, no video | shell | 15 | **0.0** |
| single_frame | one frame from the match midpoint | shell | 11 | **0.0** |
| frame_dump | 60 uniform frames, no seeking | shell | 22 | **0.0** |
| all_frames | 80 stills, one every 90 s | none | 15 | **0.0** |

All four land at zero even after submitting a full-looking answer, so nothing in
the task is obtainable without working the video. `all_frames` is the strictest of
them: the whole match is already in front of the model as a uniform sweep and the
shell is gone, so it cannot seek, crop, zoom or script — only look and answer. It
submitted 15 events and matched no rally anchor at all. `no_media` is the one that matters
most, since the NCAA rally-by-rally log for this match is public: forced to answer,
the model produced 15 plausible-looking events and matched none of them. The per-event
score anchors and blocker/hitter pairs are not recallable.

## Is the answer key visible in the video?

`observability/` answers this field by field rather than in summary.
`observability/witness.md` lists, for every one of the 23 points, each credited blocker
and the blocked hitter, whether it is legible in the post-point window and at which
offset, with the frame strip it was read from in `observability/witness/`.

| | events |
|---|---|
| every credited blocker legible | **11 / 23** |
| some credited blockers legible | 4 / 23 |
| no credited blocker legible | 8 / 23 |
| blocked hitter legible | **1 / 23** |
| blocked hitter plausible but occluded | 2 / 23 |
| blocked hitter not legible | 20 / 23 |

Every event's anchor — set and exact score-after, what the scorer matches on before it
looks at a name — is confirmed for all 23 from the score bug itself, with the read-back
recorded per event in `observability/flips.json`.

The asymmetry between the two name fields is structural. The broadcast cuts to whoever
is celebrating, which is the blocking side, so the blockers resolve on most points and
the stuffed hitter almost never does. Where a number is legible it matches the answer
key; no event was found where the video contradicts the official record. An agent that
wants the hitter has to identify the player from the rally it just watched — position
and rotation — rather than by reading a number after the whistle, which is why the
scorer gives partial credit when the blockers are exact and the hitter is wrong.

The Opus run's own conclusion that blockers "face away from the camera" came from
sampling the rally rather than the close-up.

## Design note: why every target is a block point

Service aces are excluded on purpose. An ace is a single legible jersey read with the
ball landing untouched, and agents get them: in testing on this match a strong agent
identified 4 of the 5 aces while getting no block right, and a handful of
high-precision ace hits is enough to carry F1 on their own. Dropping them leaves 23
block points that each need two opposing jersey reads inside a sub-second window at
the net, so there is no legible easy class left to score off.

## Raw trajectories

Every scored run and every ablation is published whole, as the CLI wrote it, at an
immutable dataset revision. `MANIFEST.json` in that dataset repeats each hash and adds
the SHA256 of the uncompressed stream inside each archive; `rollouts/run-envelope.md`
records the CLI versions, the tool profile each run was given, and the network
envelope those streams were audited against.

| run | file | sha256 (of the .gz as served) |
|---|---|---|
| codex-fresh, Codex event stream | [`codex-fresh/rollout.jsonl.gz`](https://huggingface.co/datasets/gavinlaw/agentic-vbench-calibration-trajectories/resolve/2b90b57ba72e521de8bc0ed24c1d0470dafc5f95/usc-wsu-2023-volleyball-block-timeline/codex-fresh/rollout.jsonl.gz) (77 kB) | `5fb3f337bf11c5e619ce2a5d9f1b214718eb2481bc1ac9790b9939b0d1db8c74` |
| codex-fresh, stderr | [`codex-fresh/stderr.txt.gz`](https://huggingface.co/datasets/gavinlaw/agentic-vbench-calibration-trajectories/resolve/2b90b57ba72e521de8bc0ed24c1d0470dafc5f95/usc-wsu-2023-volleyball-block-timeline/codex-fresh/stderr.txt.gz) (4 kB) | `0a100e085160ad37b212ce18e701390f81f7cd52e57e53c6aac82e709f5a7fef` |
| opus-fresh, Claude stream-json | [`opus-fresh/rollout.stream-json.gz`](https://huggingface.co/datasets/gavinlaw/agentic-vbench-calibration-trajectories/resolve/2b90b57ba72e521de8bc0ed24c1d0470dafc5f95/usc-wsu-2023-volleyball-block-timeline/opus-fresh/rollout.stream-json.gz) (124.8 MB) | `917d683e8718dbc8ac32cb2552e4456375ee79bdc4debcfda2cec3e61a36ca35` |
| fable-interrupted | [`fable-interrupted/rollout.stream-json.gz`](https://huggingface.co/datasets/gavinlaw/agentic-vbench-calibration-trajectories/resolve/2b90b57ba72e521de8bc0ed24c1d0470dafc5f95/usc-wsu-2023-volleyball-block-timeline/fable-interrupted/rollout.stream-json.gz) (103.1 MB) | `df69c1d7cbf5a9e70fd09eb8c7a7f12c9d499e5ba21078ebe68e6bdd767a7a7b` |
| ablation, no_media | [`ablations/no_media.stream-json.gz`](https://huggingface.co/datasets/gavinlaw/agentic-vbench-calibration-trajectories/resolve/2b90b57ba72e521de8bc0ed24c1d0470dafc5f95/usc-wsu-2023-volleyball-block-timeline/ablations/no_media.stream-json.gz) (11 kB) | `bb9cc56a5d6444542f0df8b2369eea4d6dd4abc56b7fb21bac1d2b3c5722640e` |
| ablation, single_frame | [`ablations/single_frame.stream-json.gz`](https://huggingface.co/datasets/gavinlaw/agentic-vbench-calibration-trajectories/resolve/2b90b57ba72e521de8bc0ed24c1d0470dafc5f95/usc-wsu-2023-volleyball-block-timeline/ablations/single_frame.stream-json.gz) (647 kB) | `e0e4447f1080b82565ef02e418ef473dee627d76f90e7de576be0283e1b4c05e` |
| ablation, frame_dump | [`ablations/frame_dump.stream-json.gz`](https://huggingface.co/datasets/gavinlaw/agentic-vbench-calibration-trajectories/resolve/2b90b57ba72e521de8bc0ed24c1d0470dafc5f95/usc-wsu-2023-volleyball-block-timeline/ablations/frame_dump.stream-json.gz) (3.8 MB) | `014f44c745389c5ac76b770c3876bfd5157cdb2bad8f086e6638222f36ff25b4` |

`gunzip -c <file> | sha256sum` checks the stream itself; `sha256sum <file>` checks the
archive as served. The traces carry every tool call and result, including the frames
the agents extracted, so turn counts and the no-web / no-key-access audits are
checkable without trusting this file.

Answer files, prompts, provenance and tool-call histograms for the same runs are in
`rollouts/`.
