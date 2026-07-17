# Calibration — usc-wsu-2023-volleyball-ace-block-timeline

Block-only timeline. Deterministic F1 scorer (`steps/solve/tests/judge.py`). A task
clears the bar when **every real agent scores below the ~0.10 line** (reviewer
accepts <= 0.109) and a real attempt takes **more than 50 tool-call turns**. Oracle
must be 1.0 and an empty attempt near 0.

| run | score | rollout (tool-call turns) |
|---|---|---|
| oracle | 1.0 | — |
| empty / null | 0.0 | — |
| 23-block guess (right anchors, wrong names) | 0.0 | — |
| Codex CLI (gpt-5.6-sol, xhigh) | 0.015 | 43-event attempt (>50 turns) |
| Claude Code CLI (Fable 5, xhigh) | 0.031 | ~597 tool-call turns |
| Antigravity | ~0.0 (by sister-task recipe) | not independently re-run — see note |

Oracle, empty, and the anchor-only guess are verified locally (oracle 1.0; empty and
the names-wrong guess both 0.0). Neither strong agent got a single block point fully
correct (0 full matches each) — the two-jersey net attribution (blocker multiset +
stuffed hitter) is the hard skill, and both stay far under the bar.

**Antigravity.** Not independently re-run on this match. The sister BYU task
established that a genuine, integrity-verified Antigravity 0.0 needs three cheat
vectors closed at once — server-side Gemini web grounding (always-on "pixels only, no
web" rule in AGENTS.md), local answer-file theft (workspace outside the repo with
`trustedWorkspaces` narrowed to it), and cross-conversation memory (wipe agy's local
stores before the run). That recipe applies unchanged here — same broadcast
production, same public NCAA record. This block-only task makes web grounding the
dominant risk, because the one derived field (the blocked hitter) IS named in the
public play-by-play, so an ungrounded, memory-wiped run has nothing to look up and
falls to ~0. Can be re-run under that recipe for a per-task number on request.

**Design note (ace+block -> block-only).** This task was first built as an ace+block
timeline. In calibration Fable nailed 4 of the 5 service aces — a legible
single-jersey read with the ball landing untouched — and, reporting few but precise
events, reached F1 0.24 (over the bar) purely off aces, while getting 0 blocks fully
right. Codex, over-reporting, was 0.099. Dropping the aces removes the only legible
event class: the same genuine runs re-grade to Codex 0.015 / Fable 0.031, and the
task now tests only the hard net attribution (and is distinct from the sister BYU
ace+block task).

The two agent rows above are those re-grades of the genuine, complete ace+block runs
against the block-only ground truth (their block predictions kept, ace predictions
dropped). Fresh block-only re-runs were attempted but did not complete for reasons
outside the task: the Fable resume kept hitting the Max-subscription 5-hour session
limit, and a clean block-only Codex run was cut off first by a network drop and then
by a `codex_models_manager` stall — in every attempt the agent's block attribution
was already 0 full matches, so the re-grade is the stable, defensible number. Genuine
run transcripts (Codex's 43-event ace+block output + score index; Fable's 597-turn
stream, digested) are archived under `rollouts/`.

Media baked and pinned (2026-07-15): 720p audio-stripped mp4, sha256
`13ccbabb…d08ba9e`, hosted at the dataset URL in the Dockerfile (HF commit 859cb68).

Note on `no_media`: the official NCAA rally-by-rally log for this match is public web
data. The container builds with `allow_internet = false` and the prompt forbids
lookups, so the no-media ablation measures pure model recall/guessing of that public
record; it is ≈ 0.

`frames/` holds sample frames at block moments from the baked 720p file, showing that
jersey numbers and the score bug resolve at the shipped resolution.
