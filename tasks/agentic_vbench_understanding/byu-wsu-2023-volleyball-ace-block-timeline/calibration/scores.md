# Calibration — byu-wsu-2023-volleyball-ace-block-timeline

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
`steps/solve/tests/test_judge.py` covers the scorer's tiers: 17 cases, all passing.

## Model matrix — fresh runs on the final three-attribution instruction

Each run used a workspace holding only the video and the instruction, with no prior
artifact of this task reachable; `run-metadata.txt` beside each rollout records model,
effort, schema, instruction hash and media hash.

| agent | model / setting | score | work | integrity |
|---|---|---|---|---|
| Codex CLI | gpt-5.6-sol, xhigh | **0.0189** | 29 events submitted | key 0, web 0 |
| Claude Code | Opus 5, xhigh | **0.0** | 386 tool-call turns, 23 events | key 0, web 0 |
| Antigravity | — | not run | — | — |

Both wrote their own `solution.json`, both filled all three attributions on every
event they submitted, and **neither got a single block point fully correct** — Codex
managed one partial, Opus none. Between them they identified only 2 of 18 rallies
correctly at all.

## Why the schema changed, and what it cost

This task previously asked for aces and blocks, with two attributions per block. Under
that schema it did not clear the bar: a fresh Codex run scored **0.1887**. Two things
were wrong with it.

**The aces were a giveaway.** A service ace is one legible jersey read with the ball
landing untouched, and agents get them. Dropping the 5 aces leaves only net exchanges.

**Two attributions were not enough.** Block-only alone still left Codex at 0.1333: with
19 events, two correct blocks carry a lot of recall. The scorer now also asks for the
setter who fed the blocked attack — a third jersey read, and the only one that sits
mid-rally rather than at the terminal instant, so it cannot be recovered from the
post-point celebration. The official rally log records the whole chain
(`Set by X → Attack by Y → Block by Z`), so the answer key is as solid as before.

Re-grading the block-only runs under the three-attribution scorer drops Codex from
0.1333 to 0.0426 — the two blocks it had fully right become partials, and its partials
become nothing. The fresh runs above, on the new instruction, land lower still.

One rally line in the source is corrupted (set 2 at 1-2: its name field contradicts
the box score, and neither hitter nor setter is recoverable). It is now excluded from
the key rather than carried with a hidden exemption, so the scorer no longer has a
special case the task contract does not mention.

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
obtainable without working the video. `no_media` is the one that matters most, since this match's rally-by-rally log is
public: forced to answer, the model produced 16 plausible events from recall and
matched none. The per-event score anchors and the blocker/hitter/setter triples are
not recallable.

Artifacts in `ablations/`; raw answers and provenance for the scored runs in
`rollouts/`.

## Scorer symmetry fix

The partial-credit rule was asymmetric: one wrong name in a two-player block earned
partial credit, but a solo block credited to the wrong player earned nothing. Errors
are now counted as `max(unmatched-GT, unmatched-pred)`, so a substitution is one error
either way, and solo-wrong, solo-missing, solo-extra and one-wrong-pair sit in the same
tier. The name-ambiguity table is also computed over setters now, not just blockers and
hitters, so a setter who appears nowhere else in the key still participates in the
unambiguous-lastname rule.

## A note on the numbers this file used to carry

Earlier versions reported Codex 0.02, Fable 0.15, Opus 4.8 0.0 and Antigravity 0.0.
Those runs were made against the pre-hardening instruction, which did not ask for the
blocked hitter, and were then graded under the hardened scorer — so none of them could
score full credit on any block no matter how good they were. They measured a schema
the task no longer ships. They have been replaced by the fresh runs above rather than
carried forward, and the lesson is recorded here because it is easy to repeat: after
changing a task's schema, re-run the agents; do not re-grade their old answers.
