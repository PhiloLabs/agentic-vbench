# Rollouts

This directory contains compact calibration artifacts for local strong-agent
rollouts.

The qualifying long-horizon rollout is
`codex-local-chess-gt50-20260710T213945Z`: it scored `0.033` and used 54
distinct shell/tool turns, satisfying the current hardness and rollout-length
gates.

Additional Codex, Claude, and Antigravity runs are included as supporting
failure evidence. Bulky raw trajectory files may be omitted from the repository
when the corresponding `run-summary.md`, reward files, and checker outputs
capture the relevant outcome.
