# Codex Rollout Summary

- Agent: Codex CLI (`codex exec`, fresh clean local workspace)
- Run id: `codex-local-chess-20260710T205129Z`
- Workspace: local calibration workspace `calibration_runs/otb-chess-move-capture-reconstruction/codex-local-chess-20260710T205129Z`
- Prompt variant: task prompt with `/workspace` paths rewritten to the run workspace
- Source material: `materials/game.mp4`, copied from the benchmark masked board video
- Reward: `0.0058` under the current windowed content matcher
- Checks: `2/343` passed
- Predicted moves: `36` plies vs `115` expected
- Predicted captures: `11` capture events vs `22` expected
- Passed checks: `result` only (`white_win`)
- Tool/trajectory count: `36` distinct shell command executions (`34` completed, `2` failed), `149` JSONL records, `72` completed agent messages
- Repo checker result: passed structure/oracle/baseline/strong-agent reward checks, failed the `rollout > 50 turns` gate when `agent-turns` is counted as `36` distinct shell command executions
- Operational issues: several attempted image inspections used incorrect local paths; the agent later recovered by generating additional crops. The final answer was produced without manual repair.
- Other agents: Claude Code and Antigravity were run later as supporting calibration evidence.

The Codex run reconstructed a short legal-looking line beginning `1. e4 d5 2. Nf3 Nc6`, but the ground truth begins `1. Nf3 Nf6 2. c4 e6`. The verifier therefore awarded very little move/capture identity or timing credit.
