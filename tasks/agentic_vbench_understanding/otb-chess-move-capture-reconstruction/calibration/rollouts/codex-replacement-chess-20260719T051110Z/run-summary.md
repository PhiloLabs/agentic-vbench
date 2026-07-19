# Codex Replacement-Source Rollout Summary

- Agent: Codex CLI 0.144.0-alpha.4, `gpt-5.6-sol`, high reasoning
- Run id: `codex-replacement-chess-20260719T051110Z`
- Launch mode: fresh ephemeral session with user configuration and rules ignored,
  a new local workspace, and workspace-write sandboxing
- Source: silent 1280x720 replacement video, SHA-256
  `b9839b0e67c02ffa4ae9a7662809b25a045f6feff9749844bb66eb19d6a99420`
- Prompt variant: benchmark instruction with `/workspace` rewritten to the clean
  local workspace plus an explicit requirement for at least 51 substantive
  shell-tool calls
- Reward: `0.0250` (`9/360` checks passed)
- Submission: `black_win`, 60 predicted plies, and 18 predicted captures versus
  104 plies and 26 captures in the corrected ground truth
- Conservative rollout length: 142 completed shell-command records (134
  successful and 8 failed)
- Runtime: just under 60 minutes
- Other agents: Claude Code and Antigravity were not run

The rollout correctly identified the Black win and the first four move
identities (`1.e4 e5 2.Nf3 Nc6`). It also placed the first three timestamps
within tolerance and matched `...d6` later inside the verifier's ply window.
The reconstruction diverged at `3.Bb5`, and the final submission stopped at
ply 60 (`30...Kh7`) despite inspecting the video through the end.

The agent used full-video contact sheets, perspective-warped board views,
quarter- and half-second frame checks, square labels, pixel differences, and a
final schema/capture audit. The failed commands were recoverable ImageMagick
syntax/path attempts and one non-git workspace check. Near the end, the Codex
stream retried five times and fell back to HTTP without losing the session.

This rollout passes the numerical hardness and turn-count gates. It is retained
as an enforced-long-horizon diagnostic, not as the requested natural-prompt
acceptance run, because the local prompt explicitly required the minimum call
count. A fresh full-media Codex run using only the benchmark instruction remains
the clean acceptance follow-up.
