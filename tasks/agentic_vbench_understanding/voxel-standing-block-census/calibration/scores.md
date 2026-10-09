# Calibration — voxel-standing-block-census

Deterministic scorer (`steps/solve/tests/judge.py`): the fraction of the 180
(checkpoint, block type) cells whose count is exactly right. No gate. A task
clears the bar when every real agent scores below 0.10, a real attempt takes
more than 50 tool-call turns, and every degraded-input arm stays at or below
0.15.

## How the calibration was run

The strong-agent run acts on the image `environment/Dockerfile` builds,
started frozen and without a network:

```
docker run -d --network none --cpus 4 --memory 8g <image> sleep infinity
```

The agent CLI stays on the host, because it needs a network to reach its own
API, and is given no direct access to the task. Its only two tools are `exec`,
which runs a command inside the container with `/workspace` as the working
directory, and `fetch`, which copies one file out so that a frame can be
opened as an image. The recording, the agent's own scratch files and the
answer it writes all live inside the container; `generator/container_mcp.py`
is the proxy, and `generator/run_arm.sh` the runner.

For the whole of a run the directory holding the ground truth and the
generator is mode 000 on the host, and the agent's own sandbox is read-only,
so it cannot change that back. Both halves were checked: a read-only sandboxed
process gets `Operation not permitted` from `chmod` and `Permission denied`
from `cat`. As a second, independent check, every host path appearing anywhere
in the run transcript was collected and compared against the arm directory.

All three agent arms were run this way. Codex and Claude Code reach the
container through the MCP proxy above. Antigravity refuses that route: it
executes commands inside a sandbox of its own that denies the docker socket,
and every denied command escalates to a prompt a person has to answer, so an
unattended run is impossible through it. That arm therefore reaches the same
container through a file bridge instead, `generator/bridge_daemon.py` with
`generator/task_bridge_client.sh` as the client the agent calls: the agent
writes a command into a file in its own workspace and reads the result back
from another, and an unsandboxed process on the host is the only thing that
speaks to docker. It ran to completion with no human intervention.

The three degraded-input arms were not run this way. Each one exists to
withhold something — the recording, all but one frame, the tools — so the
container would have nothing to serve them, and the input each was given is
recorded with its transcript instead.

Checked inside the container before the run:

| check | result |
|---|---|
| `sha256sum /workspace/materials/session.mp4` | matches the digest in §9 |
| name lookup for an external host | `socket.gaierror`, no network |
| judge on the truth file | `reward 1.0` |
| judge on an empty submission | `reward 0.0` |

## Runs

| run | reward | tool-call turns |
|---|---|---|
| oracle (the rig's own log replayed) | 1.0000 | — |
| empty submission | 0.0000 | — |
| Codex CLI (gpt-6-astra, high), in the container, **final** | 0.0556 | 104 |
| Codex CLI (gpt-6-astra, high), on the host, earlier | 0.0389 | 74 |
| Antigravity (Gemini 3.8 Flash, medium), in the container | 0.0056 | 165 |
| Claude Code (Opus 5, high), in the container | did not finish, see below | 318 |
| no_media (final ablation) | 0.0333 | 0 |
| single_frame (final ablation) | 0.0056 | 0 |
| frame_dump_no_tools (final ablation) | 0.0056 | 0 |

The Codex run answered all thirty checkpoints and reported having tallied the
whole recording, so it is a completed attempt rather than an abandoned one.
Its early checkpoints carry most of what it got right and its error grows with
elapsed time: of the ten cells it placed exactly, nine fall in the first three
checkpoints and one at t=1140, and nothing after that is right. The growth is
the cumulative metric carrying each miss forward. The misses themselves happen
minute by minute. Its per-minute change in each cell is exactly right in 15.6
per cent of the 180 cells and within one in 42.8 per cent, and its per-minute
total is right in only 2 of the 30 minutes, while the mix of types it reports
stays close to the truth (total variation distance 0.090). It names what it
sees and misses what changes, which is why `SPEC.md` files this task under
perception. Raw transcript in `rollouts/final/codex-container.jsonl.gz`, its
104 proxied actions in `codex-container-tool-calls.txt`.

The same model, given the same recording on the host instead, scored 0.0389 in
74 turns. Working through the proxy it took more turns and scored a little
higher, and the headline figure above is the higher of the two.

## Every ablation was run twice

Asked plainly, all three degraded arms declined rather than guessing:

- `no_media`: "No video or placement/removal history was provided. The block
  counts at the requested times cannot be determined from this prompt alone."
- `single_frame`: "The attached frame cannot establish counts at the 30
  requested times."
- `frame_dump_no_tools`: "I can't reliably distinguish and track every placed
  block across these contact sheets well enough to give exact counts."

A refusal scoring zero is not evidence that the degraded input cannot be used;
it is evidence the model would not guess. Each arm was re-run with declining
ruled out and a best estimate demanded, and the table above reports those
runs. Both transcripts are kept: `*_raw_first_attempt.jsonl.gz` is the
refusal, `*_raw.jsonl.gz` the forced answer, with the two prompts alongside.

Note that `frame_dump_no_tools`, given the entire recording at one frame per
second — 1824 frames in 38 contact sheets, in `rollouts/final/full_dump/` —
scores no better than `single_frame`. Without tools the extra 1823 frames add
nothing, which is what this ablation exists to establish.

## Attacks on the scorer

Using only what the prompt states or what can be estimated off the video
without tracking anything:

| arm | reward |
|---|---|
| all zero | 0.0000 |
| every cell = 45 / 65 / 85 | 0.0000 / 0.0056 / 0.0222 |
| total linear in time to the true final, split evenly | 0.0222 |

Handed pieces of the answer key. These bound the corresponding real attack
rather than baselining it:

| arm | reward |
|---|---|
| exact per-checkpoint total, split evenly | 0.0500 |
| exact per-checkpoint total, split by the whole-video type mix | 0.0500 |
| honest tracking that misses 2% of events | 0.1722 |
| honest tracking that misses 5% | 0.1333 |
| honest tracking that misses 10% | 0.0222 |
| honest tracking that misses 20% | 0.0000 |
| perfect tracking with the clock 10 s out | 0.4167 |
| perfect tracking that ignores removals entirely | 0.1556 |

Reproduce from the task directory with

    python3 generator/controls6b.py generator/rig_events.tsv 4.13

whose first block (30 checkpoints) is the table above. It also prints the same
attacks on the first 15 minutes, which is a different, easier span and not the
shipped task.

## Claude Code (Opus 5) did not finish

It spent the whole of the task's own four-hour budget on a pipeline it never
got to run to the end: a frame-by-frame differencing pass over all 21,600
frames, which yielded 3,021 candidate events and 6,042 thumbnails, then a
second feature pass over those candidates in 51 parallel chunks, then a third
it had only just started when the budget ran out. `output/solution.json` was
never written, so the arm scores zero by not finishing rather than by being
wrong, and the table records it as such. Its 318 proxied actions are in
`rollouts/final/opus5-container-tool-calls.txt` and the transcript in
`opus5-container.jsonl.gz`.

The instruction file does not ask for an answer to be written early and
revised. Codex wrote one and improved it; this arm did not, and the difference
shows up as an arm with nothing to score. That is a property of the run, not of
the task, and it is reported here rather than folded into the difficulty
figure, which rests on the Codex arm.

## Antigravity (Gemini 3.8 Flash, medium)

0.0056, one of the 180 cells, at the t=1200 checkpoint. It answered all thirty
checkpoints and reported having worked the whole recording.

Its method is visible in the run and is the one this task is built to defeat:
it pulled a single frame at each of the thirty checkpoints and counted
connected components of each type's colour inside that one frame. That counts
what happens to be in shot, not what is standing, and it needs no history at
all, so the counts track what the camera happens to be pointing at rather
than what has accumulated. Early on that overshoots, because terrain of a
similar colour is counted too: 63 standing at t=60 against a true 37. Later
it undershoots badly, because most of what is standing is out of shot: 289
at t=1800 against a true 547.

The answer is at `rollouts/final/gemini-container-solution.json`, its 165
proxied actions at `gemini-container-tool-calls.txt`, the instruction file it
was given at `gemini-container-instructions.md`, and the raw trajectory the
application wrote, all 320 steps, at `gemini-container.jsonl.gz`. The run was
started from the application with Gemini 3.8 Flash at medium selected in its
model menu. That trajectory names no model, so the identity is recorded from
the conversation's own store: all 160 planner steps carry
`MODEL_PLACEHOLDER_M319`, the identifier the application saved for that
selection, and not `M322`, which is what its headless `flash` tier resolves to.
