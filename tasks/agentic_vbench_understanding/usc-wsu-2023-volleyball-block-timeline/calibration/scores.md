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
`steps/solve/tests/test_judge.py` covers the scorer's tiers: 17 cases, all passing.

## Model matrix — fresh runs on the final block-only instruction

Every run below used a workspace containing only the video and the instruction, with
no prior artifact of this task reachable; `run-metadata.txt` beside each rollout
records CLI version, model, effort, instruction hash, media hash and judge commit.

| agent | model / setting | score | tool-call turns | integrity |
|---|---|---|---|---|
| Codex CLI | gpt-5.6-sol, xhigh | **0.0185** | 160 items / 289 commands | key 0, web 0 |
| Claude Code | Opus 5, xhigh | **0.0** | 270 | key 0, web 0 |
| Claude Code | Fable 5, xhigh | not scored | 210 before the account ran out of credits | key 0, web 0 |
| Antigravity | — | not run | — | — |

Both scored runs ended normally rather than being cut off, and both wrote their own
`solution.json`. Codex submitted 31 events and got **no block fully correct** (one
partial). Opus submitted a single event, and said so plainly: it rebuilt the entire
200-rally timeline from the score bug — reconciling exactly with the final box score,
including two overturned challenges — then reported that it could confirm only one
block point, and that even there the blocker credit was "an inference, not a reading".

That is the intended shape of this task. The timeline layer is tractable; the
attribution layer is not, unless the agent finds the one place it is visible.

Fable's run is archived but unscored: it reached 210 tool-call turns of genuine frame
work before the account's credit pool for that model ran out, so no answer was
written. Reporting a number for it would misrepresent an interrupted run.

## Ablations

Run on the same instruction. A model that declines to answer measures nothing, so
each ablation also demands a best-effort answer; the counts below are what the model
actually submitted.

| ablation | inputs | events submitted | score |
|---|---|---|---|
| no_media | instruction only, no video | 15 | **0.0** |
| single_frame | one frame from the match midpoint | 11 | **0.0** |
| frame_dump | 60 uniform frames, no seeking | 22 | **0.0** |

All three land at zero even after submitting a full-looking answer, so nothing in
the task is obtainable without working the video. `no_media` is the one the review
asked about specifically, since the NCAA
rally-by-rally log for this match is public: forced to answer, the model produced 15
plausible-looking events and matched none of them. The per-event score anchors and
blocker/hitter pairs are not recallable.

## Is the answer key visible in the video?

`observability/` carries the ledger: the exact second each of the 23 points is
awarded (derived verifier-side by OCR'ing the score bug, independent of any agent),
four frames per event spanning the post-point close-up, and what can be read off
them. Summary of the finding:

- the wide sideline shot never resolves jersey numbers, and the broadcast shows no
  replays;
- a net close-up 0.8-3.2 s after each point does resolve them, and that window is the
  only place attribution is recoverable;
- on every event examined across that full window the credited blockers were legible
  and matched the answer key; the blocked hitter is legible less often, which the
  scorer already handles with partial credit.

So the information is present but narrowly placed — hard, not impossible. The Opus
run's own conclusion that blockers "face away from the camera" came from sampling the
rally rather than that window.

## Design note: why block-only

Built first as an ace+block timeline. In calibration Fable nailed 4 of the 5 service
aces — a legible single-jersey read with the ball landing untouched — and, reporting
few but precise events, reached F1 0.24 off aces alone while getting no block right;
Codex, over-reporting, was 0.099. Dropping the aces removes the only legible event
class, leaving 23 block points that each need two opposing jersey reads. It also
makes this task distinct from the sister BYU ace+block task.

Raw trajectories for every scored run are in `rollouts/`.
