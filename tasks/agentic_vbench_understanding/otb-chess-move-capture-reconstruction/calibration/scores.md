# Calibration Scores

This task is in post-review revision. Oracle/null behavior is healthy, but the
current source and calibration do not yet satisfy all submit-ready gates.

| run | status | reward | notes |
|---|---:|---:|---|
| oracle | passed | 1.0 | Static oracle solution copied from the built ground truth; 297/297 checks passed. |
| empty baseline | passed | 0.0 | Empty `moves` and `capture_events` submission; 0/297 checks passed. |
| Codex CLI (`codex-local-chess-20260710T205129Z`) | completed | 0.0058 | Fresh clean workspace; produced 36 plies and 11 capture events; 2/343 checks passed under the windowed content matcher. Reward gate passed, but the long-horizon rollout gate failed (`36` distinct shell commands, need `>50`). Archive: `calibration/rollouts/codex-local-chess-20260710T205129Z/`. |
| Claude Code CLI (`claude-local-chess-20260710T223658Z`) | session-limit failure | 0.0 | Fresh local Claude Code rollout; no `output/solution.json` was produced before Claude hit a 429 session limit. Judge scored the missing file as an empty/unreadable submission: 0/297 checks passed. A slim trajectory is archived because the raw transcript was too large for review. Archive: `calibration/rollouts/claude-local-chess-20260710T223658Z/`. |
| Antigravity CLI (`antigravity-local-chess-fixed-default-20260711T034259Z`) | stopped by cap / no solution | 0.0 | Fresh local Antigravity retry after runner fixes; no `output/solution.json` was produced before the external watchdog stopped it at transcript `max_step=58`. Strict conservative tool-call count was only `27`, so this does not satisfy the `>50` rollout-length gate. Archive: `calibration/rollouts/antigravity-local-chess-fixed-default-20260711T034259Z/`. |

## Post-Review Required Work

- Replace the current source video or neutralize the source distribution so the
  PGN is not recoverable from public metadata.
- Rebuild ground truth as `human-verified` with 2+ independent timestamp
  annotation passes.
- Run `single_frame` and `no_media` ablations against the replacement source.
- Recalibrate with natural prompts only; do not count prompt-padded turn runs.
