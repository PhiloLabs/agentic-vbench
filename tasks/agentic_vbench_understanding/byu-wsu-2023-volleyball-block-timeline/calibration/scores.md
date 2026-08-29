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

## Model matrix

Each run used a workspace holding only the video and the instruction, with no prior
artifact of this task reachable. The exact prompt is `rollouts/instruction-as-run.md`;
`run-metadata.txt` beside each rollout records model, effort, schema, and the
instruction and media hashes.

| agent | model / setting | score | work | integrity |
|---|---|---|---|---|
| Codex CLI | gpt-5.6-sol, xhigh | **0.0213** | 71 tool-call items, 29 events submitted | key 0, web 0 |
| Claude Code | Opus 5, xhigh | **0.0** | 386 tool-call turns, 23 events submitted | key 0, web 0 |
| Antigravity | — | not run | — | see `../agent-integrity/` |

Both wrote their own `solution.json` and filled all three attributions on every event
they submitted, and **neither got a single block point fully correct** — Codex managed
one partial, Opus none. Between them they located 3 of the 18 rallies at all (matching
set and score-after); on those three, the attributions were still wrong.

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

| ablation | inputs | events submitted | score |
|---|---|---|---|
| no_media | instruction only | 16 | **0.0** |
| single_frame | one frame from the match midpoint | 9 | **0.0** |
| frame_dump | 60 uniform frames, no seeking | 16 | **0.0** |

All three land at zero after submitting a full-looking answer, so nothing here is
obtainable without working the video. `no_media` is the one that matters most, since
this match's rally-by-rally log is public: forced to answer, the model produced 16
plausible events from recall and matched none. The per-event score anchors and the
blocker/hitter/setter triples are not recallable.

Artifacts in `ablations/`; answers, prompt and provenance for the scored runs in
`rollouts/`; the Antigravity web-grounding finding in `agent-integrity/`.
