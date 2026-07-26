# Calibration — ne-atl-2017-super-bowl-li-penalty-timeline

Deterministic F1 scorer (`steps/solve/tests/judge.py`). A task clears the bar when
**every real agent scores below 0.10** and a real attempt takes **more than 50
tool-call turns**. Oracle must be 1.0 and an empty attempt 0.

| run | score | rollout (tool-call turns) |
|---|---|---|
| oracle (pilot subset) | 1.0 | — |
| empty / null | 0.0 | — |
| plausible guess | 0.0 | — |
| no_media (indicative proxy) | 0.0 | 0 |
| GPT 5.6 Sol | _to run_ | _to run_ |
| Codex CLI | _to run_ | _to run_ |
| Antigravity | _to run_ | _to run_ |

Status: PRE-CALIBRATION. Oracle / empty / no_media verified locally. The three-agent
calibration (GPT 5.6 Sol first, per the README) has not been run — it requires the
maintainer's agent stack and is the gating step before this task is PR-ready. Raw
trajectories will be added under `rollouts/` once run.

Notes on what is already measured:
- no_media: a strong model with no media and no tools reconstructed 0 of 13 accepted
  penalties. Indicative (proxy model, not GPT 5.6 Sol), but de-risks the fame concern.
- audio intelligibility: the referee's announced jersey number transcribed cleanly on a
  small CPU ASR model for 4/4 sampled player fouls (#70, #23, #34, #59).
