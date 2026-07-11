# Codex Rollout Summary

- Agent: Codex CLI (`codex exec`, fresh clean local workspace)
- Run id: `codex-local-chess-gt50-20260710T213945Z`
- Workspace: `/Users/brendaz/Documents/Codex/2026-07-07/tak/work/agentic-vbench/calibration_runs/otb-chess-move-capture-reconstruction/codex-local-chess-gt50-20260710T213945Z`
- Prompt variant: task prompt with `/workspace` paths rewritten to the run workspace, plus an explicit calibration instruction requiring at least 51 meaningful shell/tool turns before finalizing
- Source material: `materials/game.mp4`, copied from the benchmark masked board video
- Reward: `0.033`
- Checks: `10/303` passed
- Predicted moves: `35` plies vs `115` expected
- Predicted captures: `7` capture events vs `22` expected
- Passed checks: result plus the identity/timing checks for the first four plies
- Tool/trajectory count: `54` distinct shell command executions (`51` completed, `3` failed), `274` JSONL records, `161` completed agent messages
- Repo checker result: passed structure, oracle, baseline, strong-agent reward, and `rollout > 50 turns` gates when `agent-turns` is counted as `54` distinct shell command executions
- Operational issues: OpenCV and python-chess were unavailable; Codex used PIL-based crops and a local lightweight legality validator. Three shell commands failed during inspection/validation and were recovered from inside the rollout.
- Other agents: Claude Code and Antigravity were intentionally not run per the user request.

This run improved over the first Codex rollout by correctly identifying the opening `1. Nf3 Nf6 2. c4 e6`, but it diverged at ply 5 by predicting `d4` instead of the ground-truth `e3`, then reconstructed a shorter 35-ply legal-looking game.
