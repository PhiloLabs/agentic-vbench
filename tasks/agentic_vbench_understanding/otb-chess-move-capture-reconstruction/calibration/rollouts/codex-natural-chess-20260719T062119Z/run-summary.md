# Natural-Prompt Codex Rollout Summary

- Agent: Codex CLI 0.144.2, `gpt-5.6-sol`, high reasoning
- Run id: `codex-natural-chess-20260719T062119Z`
- Launch mode: fresh ephemeral session with user configuration and rules ignored,
  a new local workspace, and workspace-write sandboxing
- Source: silent 1280x720 replacement video, SHA-256
  `b9839b0e67c02ffa4ae9a7662809b25a045f6feff9749844bb66eb19d6a99420`
- Prompt variant: exact benchmark instruction with only the two `/workspace`
  paths rewritten to the clean local workspace; normalizing those paths restores
  the benchmark instruction byte for byte
- Reward: `0.0379` (`13/343` checks passed)
- Submission: `black_win`, 45 predicted plies, and 17 predicted captures versus
  104 plies and 26 captures in the corrected ground truth
- Conservative rollout length: 237 completed shell-command records (231
  successful and 6 failed)
- Runtime: 35 minutes 18 seconds
- Other agents: Claude Code and Antigravity were not run

The rollout correctly identified the Black win and the first five move
identities (`1.e4 e5 2.Nf3 Nc6 3.Bb5`), with their timestamps inside the
verifier tolerance. It diverged at ply 6 by recording `3...a6` instead of
`3...Nge7`, reconstructed an incompatible continuation, and stopped at 45
plies with `23.O-O-O` despite inspecting the video through the end.

The agent used full-video contact sheets, perspective-warped board views,
high-frequency frame sampling, image differences, square labels, and
square-level pixel comparisons. It attempted only offline package/tool
discovery and did not browse or look up the game. It did violate the prompt's
workspace-boundary rule by writing analysis frames under `/tmp/chess_recon`
and searching local system paths for chess tooling; neither location exposed
the task ground truth or prior rollout artifacts.

This is the natural-prompt full-media acceptance run requested by review. Its
`0.0379` reward passes the strong-agent hardness gate (`< 0.10`), and its 237
completed tool-call turns pass the long-horizon gate (`> 50`) without a
minimum-turn instruction or pacing hint.
