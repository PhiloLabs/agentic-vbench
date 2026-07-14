# Rollouts

This directory contains compact calibration artifacts for local strong-agent
rollouts.

After review, the earlier prompt-padded Codex rollout was removed from the PR
package. The remaining natural Codex rollout scored `0.0058` under the current
windowed content matcher but used only 36 distinct shell/tool turns, so the task
still needs real hardening before it can satisfy the long-horizon gate.

The retained artifacts are deliberately compact: one audit transcript per agent
where practical, plus `run-summary.md` files and the aggregate `scores.md`.
