# Calibration — byu-wsu-2023-volleyball-block-timeline

Block-only timeline, 18 block points, three attributions per point (the credited
blocker(s), the hitter who was blocked, and the setter who fed that attack).
Deterministic F1 scorer (`steps/solve/tests/judge.py`). A task clears the bar when
every real agent scores under the ~0.10 line and a real attempt takes more than 50
tool-call turns. Oracle must be 1.0 and an empty attempt near 0.

## Invariants, from the built image

Built clean (`docker build --no-cache`) from `environment/Dockerfile`, which pulls the
media at a pinned dataset revision and verifies its SHA256 during the build:

| run | reward |
|---|---|
| oracle (`steps/solve/solution/solve.sh`) | **1.0** |
| null (`{"events": []}`) | **0.0** |

Media inside the image hashes to `ee887b18…8796dc60`, matching the pin.
`steps/solve/tests/test_judge.py` covers the scorer's tiers and re-grades every answer
committed under `rollouts/` and `ablations/`, so the numbers below are a test failure
if they ever drift from the scorer.

The official record holds 19 block points and the key holds 18: the 19th (set 2 at 1-2)
is corrupted in the source and has no answerable attribution. Reporting it is correct
play, so the scorer sets a prediction anchored there aside — it earns nothing and costs
nothing — rather than charging it as a false positive.

## Model matrix

Each run used a workspace holding only the video and the instruction, with no prior
artifact of this task reachable. The exact prompt is `rollouts/instruction-as-run.md`;
`run-metadata.txt` beside each rollout records model, effort, schema, and the
instruction and media hashes.

Both agents were run twice: once on the calibration host, and once confined to the
shipped task image, where every action on the video happens inside a container built
from `environment/Dockerfile` with `--network none`. **The confined runs are the ones
that describe the task**; `parity/README.md` explains the confinement and
`parity/environment.txt` records the image digest and tool inventory.

| agent | model / setting | in the task image | on the host | integrity |
|---|---|---|---|---|
| Codex CLI | gpt-5.6-sol, xhigh | **0.0426** | 0.0213 | 1365 model calls, 0 other hosts |
| Claude Code | Opus 5, xhigh | 0.0 *(provisional)* | 0.0 | key 0, web 0 |
| Antigravity | — | not run | — | see `../agent-integrity/` |

The Codex row is measured with **the agent itself running inside the task image**, so
every command it issues uses that image's tools and the host contributes nothing but
model transport. Egress is default-deny behind an allowlisting proxy, and that proxy's
log shows the run never asked for a host outside the backend. `parity/README.md` has
the construction and the verification.

The Opus row is provisional: it was measured with an earlier harness that confined
access to the video but not the processing of the frames that came out of it, and it
has not been rerun. The same flaw inflated an earlier Codex figure of 0.0952 —
confining the processing brought it to 0.0426.

Inside the image Codex submitted 29 events over 232 command executions and five hours,
matched 9 of the 18 rally anchors, and got one block point **fully correct** — set 1 at
18-14, with both blockers, the stuffed hitter and the setter all right. That single
event is the only fully-correct one on either task, and it survives every version of
the harness.

Finding the rallies is what the environment changes. Given host tooling a batch pass
over the score bug is cheap and 11 anchors fall out; inside the image the same work
costs more and 9 do. Attribution does not move — one event either way. Tooling helps
with the tedious layer, which is why the field the task leans on is the one no camera
angle hands over.

## Design note: why three attributions

Eighteen events is a small denominator, so full credit has to be genuinely hard to
earn or a couple of lucky reads dominate the score: two fully correct blocks inside a
tight ten-event answer would already be F1 ≈ 0.14.

The three attributions are not equally reachable, and that is the point. The
blocker(s) and the stuffed hitter are both at the net at the terminal instant, and the
broadcast cuts to a close-up there moments after the whistle — an agent that finds
that window can read them together. The setter touched the ball seconds earlier,
mid-rally, in the wide sideline shot, and can only be recovered by tracking the rally
back from its ending. The official log records the whole chain
(`Set by X → Attack by Y → Block by Z`), so the answer key is exact for all three.

Scorer sensitivity, measured on the two answers above: dropping the setter requirement
and grading on blockers + hitter alone leaves both scores unchanged (0.0213 and 0.0).
Neither agent lost a block point *because of* the setter — they missed the net
attribution as well.

## Ablations

Each ablation removes the video work and demands a best-effort answer anyway — a model
that declines to answer measures nothing. Model: Claude Code CLI, Sonnet, effort high,
same instruction as the real task.

| ablation | inputs | tools | events submitted | score |
|---|---|---|---|---|
| no_media | instruction only | shell | 16 | **0.0** |
| single_frame | one frame from the match midpoint | shell | 9 | **0.0** |
| frame_dump | 60 uniform frames, no seeking | shell | 16 | **0.0** |
| all_frames | 77 stills, one every 90 s | Read, Write | 12 | **0.0** |

All four land at zero after submitting a full-looking answer, so nothing here is
obtainable without working the video. `all_frames` is the strictest of the four and the only one whose harness had to be
built rather than trimmed. The whole match goes into context as a uniform still sweep
and the shell is taken away: no seeking, cropping, upscaling or scripting, only opening
an image and writing the answer. Two things the condition needs to be real — a model
that cannot list a directory also cannot discover filenames, so every filename is given
in the prompt; and the workspace sits outside the repository, so no judge, key or
sibling run is on a path it could open. The exact prompt is committed beside the answer
as `all_frames.instruction-as-run.md`, and the native trace is published with the rest.
It opened 76 of 77 frames, submitted 12 events and matched no block point: **0.0**. `no_media` is the one that matters most, since
this match's rally-by-rally log is public: forced to answer, the model produced 16
plausible events from recall and matched none. The per-event score anchors and the
blocker/hitter/setter triples are not recallable.

## Raw trajectories

Every scored run and every ablation is published whole, as the CLI wrote it, at an
immutable dataset revision. `MANIFEST.json` in that dataset repeats each hash and adds
the SHA256 of the uncompressed stream inside each archive; `rollouts/run-envelope.md`
records the CLI versions, the tool profile each run was given, and the network
envelope those streams were audited against.

| run | file | sha256 (of the .gz as served) |
|---|---|---|
| codex-fresh, Codex event stream | [`codex-fresh/rollout.jsonl.gz`](https://huggingface.co/datasets/gavinlaw/agentic-vbench-calibration-trajectories/resolve/2b90b57ba72e521de8bc0ed24c1d0470dafc5f95/byu-wsu-2023-volleyball-block-timeline/codex-fresh/rollout.jsonl.gz) (22 kB) | `9bcb80320fece252d553b7d3d7f5778aa316620fc36b5a8d5a2a93e49aa6767e` |
| codex-fresh, stderr | [`codex-fresh/stderr.txt.gz`](https://huggingface.co/datasets/gavinlaw/agentic-vbench-calibration-trajectories/resolve/2b90b57ba72e521de8bc0ed24c1d0470dafc5f95/byu-wsu-2023-volleyball-block-timeline/codex-fresh/stderr.txt.gz) (1 kB) | `3c45a319a3088ee3ef5839abd8cbbf69d0d3b79cfc577ef16485a761b60e522e` |
| opus-fresh, leg 1 | [`opus-fresh/rollout.leg1.stream-json.gz`](https://huggingface.co/datasets/gavinlaw/agentic-vbench-calibration-trajectories/resolve/2b90b57ba72e521de8bc0ed24c1d0470dafc5f95/byu-wsu-2023-volleyball-block-timeline/opus-fresh/rollout.leg1.stream-json.gz) (27.7 MB) | `711850547184b410d8cd593f179af9e16b75674250feabb22edea1ebe6c7ac35` |
| opus-fresh, leg 2 | [`opus-fresh/rollout.leg2.stream-json.gz`](https://huggingface.co/datasets/gavinlaw/agentic-vbench-calibration-trajectories/resolve/2b90b57ba72e521de8bc0ed24c1d0470dafc5f95/byu-wsu-2023-volleyball-block-timeline/opus-fresh/rollout.leg2.stream-json.gz) (186.7 MB) | `8e4eb6fffcac9e6f84cf2228313dfecd0b0631c10caa4f91de398ba786603e3a` |
| parity, Codex inside the task image | [`parity-v2-codex/rollout.jsonl.gz`](https://huggingface.co/datasets/gavinlaw/agentic-vbench-calibration-trajectories/resolve/ad70da550bf9b3dedd42face538268319779d751/byu-wsu-2023-volleyball-block-timeline/parity-v2-codex/rollout.jsonl.gz) (50 kB) | `9509046a03a34b7c1a1581e4c2de73cbe19d75cde200beeab236651e4bfa31d7` |
| parity, that run's egress log | [`parity-v2-codex/egress.log`](https://huggingface.co/datasets/gavinlaw/agentic-vbench-calibration-trajectories/resolve/ad70da550bf9b3dedd42face538268319779d751/byu-wsu-2023-volleyball-block-timeline/parity-v2-codex/egress.log) (72 kB) | `8ee79d1f31f5dcef70d67d9a4b678cd50ca473dcec4cbd6ac1c8485c06abf6b8` |
| parity, Codex in the task image (superseded) | [`parity-codex/rollout.jsonl.gz`](https://huggingface.co/datasets/gavinlaw/agentic-vbench-calibration-trajectories/resolve/5719e3303f366594dd471a048a69ead60e4c2bcd/byu-wsu-2023-volleyball-block-timeline/parity-codex/rollout.jsonl.gz) (45 kB) | `0d3356eb172e83e00ddf1b60a1528253dd5376366121d686b76455686faae76c` |
| parity, Opus in the task image | [`parity-opus/rollout.stream-json.gz`](https://huggingface.co/datasets/gavinlaw/agentic-vbench-calibration-trajectories/resolve/5719e3303f366594dd471a048a69ead60e4c2bcd/byu-wsu-2023-volleyball-block-timeline/parity-opus/rollout.stream-json.gz) (197.6 MB) | `f2a40d87f866603566fa5b93daabc7cb064a863f900e75e49ec1180f2063e998` |
| ablation, no_media | [`ablations/no_media.stream-json.gz`](https://huggingface.co/datasets/gavinlaw/agentic-vbench-calibration-trajectories/resolve/2b90b57ba72e521de8bc0ed24c1d0470dafc5f95/byu-wsu-2023-volleyball-block-timeline/ablations/no_media.stream-json.gz) (12 kB) | `7f85d12481c326822d4614b2422ba7ebc359c8185ad79a23bcdc6741d07248c5` |
| ablation, single_frame | [`ablations/single_frame.stream-json.gz`](https://huggingface.co/datasets/gavinlaw/agentic-vbench-calibration-trajectories/resolve/2b90b57ba72e521de8bc0ed24c1d0470dafc5f95/byu-wsu-2023-volleyball-block-timeline/ablations/single_frame.stream-json.gz) (146 kB) | `026bdd99624662ea01185055a35be77b334419faa17b1ea4b4c07a48b38c3789` |
| ablation, frame_dump | [`ablations/frame_dump.stream-json.gz`](https://huggingface.co/datasets/gavinlaw/agentic-vbench-calibration-trajectories/resolve/2b90b57ba72e521de8bc0ed24c1d0470dafc5f95/byu-wsu-2023-volleyball-block-timeline/ablations/frame_dump.stream-json.gz) (6.5 MB) | `ef2b62bc88edf6665925c21f735a2c9d75cc4ee01e7e503b9ddcd66627f928e2` |
| ablation, all_frames | [`ablations/all_frames.stream-json.gz`](https://huggingface.co/datasets/gavinlaw/agentic-vbench-calibration-trajectories/resolve/c66a1ed95a6664c1f423cc0b8f1eee4d2f242e01/byu-wsu-2023-volleyball-block-timeline/ablations/all_frames.stream-json.gz) (17.0 MB) | `76afe71d06f59262629b8c00a71e069551ae3abd9dbf534a69d5261ec171d0c3` |

`gunzip -c <file> | sha256sum` checks the stream itself; `sha256sum <file>` checks the
archive as served. The two Opus legs are one session: the first was cut off by a
network drop and resumed in place, which is what the 386-turn figure counts.

Artifacts in `ablations/`; answers, prompt and provenance for the scored runs in
`rollouts/`; the Antigravity web-grounding finding in `agent-integrity/`.

