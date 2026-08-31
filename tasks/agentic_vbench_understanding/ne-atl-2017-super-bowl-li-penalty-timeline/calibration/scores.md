# Calibration — ne-atl-2017-super-bowl-li-penalty-timeline

Deterministic F2 (β=2, recall-weighted) scorer (`steps/solve/tests/judge.py`; switched
from F1 per issue #60 review — F1 let one lucky exact row clear the 0.10 gate at
0.1429, F2 does not at 0.0943). A task clears the bar when
**every real agent scores below 0.10** and a real attempt takes **more than 50
tool-call turns**. Oracle must be 1.0 and an empty attempt 0.

| run | score | rollout (tool-call turns) |
|---|---|---|
| oracle (full 13-foul ground truth) | 1.0 | — |
| empty / null | 0.0 | — |
| plausible guess (pre-fix prompt) | 0.0 — stale, rerun pending | — |
| no_media (indicative proxy, pre-fix prompt) | 0.0 — stale, rerun pending | 0 |
| GPT 5.6 Sol | _to run_ | _to run_ |
| Codex CLI | _to run_ | _to run_ |
| Antigravity | _to run_ | _to run_ |

`scripts/understanding/check_task.py` — PASS on every check not requiring the agent run:
task structure (all required files), input video (143.1 min, **1080p**, confirmed by the
checker's ffprobe), oracle == 1.0, baseline == 0.0. The agent-reward, agent-turns, and
ablation inputs are reported SKIP (they need the strong-agent stack).

Status: PRE-CALIBRATION. Oracle / empty verified locally against the current prompt.
`no_media` and `plausible guess` were run against the prompt **before** the leaked
example rows in `instruction.md` were fixed (issue #60 review) — both must be rerun
against the current prompt before being counted. The three-agent calibration (GPT 5.6
Sol first, per the README) has not been run — it requires the maintainer's agent stack
and is the gating step before this task is PR-ready. Raw trajectories will be added
under `rollouts/` once run.

Notes on what is already measured:
- no_media (stale, pre-fix): a strong model with no media and no tools reconstructed 0
  of 13 accepted penalties. Indicative (proxy model, not GPT 5.6 Sol); de-risks the fame
  concern but needs rerunning on the fixed prompt with the named strong model.
- audio intelligibility: the referee's announced jersey number transcribed cleanly on a
  small CPU ASR model for 4/4 sampled player fouls (#70, #23, #34, #59) — all 4 are
  accepted fouls; the 3 declined fouls kept in scope are not yet audio-verified (see
  PROVENANCE.md).
