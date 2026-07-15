# Calibration — usc-wsu-2023-volleyball-ace-block-timeline

Deterministic F1 scorer (`steps/solve/tests/judge.py`). A task clears the bar when
**every real agent scores below 0.10** and a real attempt takes **more than 50
tool-call turns** (reviewer accepts <= 0.109). Oracle must be 1.0 and an empty
attempt near 0.

| run | score | rollout (tool-call turns) |
|---|---|---|
| oracle | 1.0 | — |
| empty / null | 0.0 | — |
| 28-entry guess (right anchors, wrong names) | 0.0 | — |
| Antigravity | _to run_ | _to run_ |
| Codex CLI | _to run_ | _to run_ |
| Claude Code CLI | _to run_ | _to run_ |

Oracle, empty, and the anchor-only guess are verified locally (oracle 1.0; empty and
the names-wrong 28-entry guess both 0.0). Media is baked and pinned (2026-07-15):
720p audio-stripped mp4, sha256 `13ccbabb…d08ba9e`, hosted at the dataset URL in the
Dockerfile (HF commit 859cb68; served Content-Length 1503364332 matches the local
bake). The three agent rows are pending calibration rollouts.

Raw transcripts go in `rollouts/` — one file per agent, so a reviewer can confirm
each score was earned honestly and count the tool-call turns.

Note on `no_media`: the official NCAA rally-by-rally log for this match is public
web data. The container builds with `allow_internet = false` and the prompt forbids
lookups, so the no-media ablation measures pure model recall/guessing of that public
record; the measured row (to be added) verifies it is ≈ 0.

`frames/` (added with calibration) will hold sample frames at block moments from the
baked 720p file, showing that jersey numbers resolve at the shipped resolution.
