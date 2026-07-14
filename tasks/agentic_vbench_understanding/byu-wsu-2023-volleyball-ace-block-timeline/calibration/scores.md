# Calibration — byu-wsu-2023-volleyball-ace-block-timeline

Deterministic F1 scorer (`steps/solve/tests/judge.py`). A task clears the bar when
**every real agent scores below 0.10** and a real attempt takes **more than 50
tool-call turns**. Oracle must be 1.0 and an empty attempt near 0.

| run | score | rollout (tool-call turns) |
|---|---|---|
| oracle | 1.0 | — |
| empty / null | 0.0 | — |
| 24-entry guess | 0.0 | — |
| Antigravity | _to run_ | _to run_ |
| Codex CLI | _to run_ | _to run_ |
| Claude Code CLI | _to run_ | _to run_ |

Raw transcripts are in `rollouts/` — one file per agent, so a reviewer can confirm
each score was earned honestly and count the tool-call turns.
