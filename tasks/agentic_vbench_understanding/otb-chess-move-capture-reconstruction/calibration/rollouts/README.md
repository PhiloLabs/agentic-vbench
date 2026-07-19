# Rollouts

This directory contains compact calibration artifacts for local strong-agent and
anti-shortcut rollouts.

The Codex, Claude, and Antigravity full-media runs predate the replacement source
and are retained only as historical review context. They do not count toward
acceptance for the current task material.

The replacement-source `single_frame` and `no_media` Codex ablations are recorded
here as compact rewards and run summaries. Their bulky local workspaces are kept
out of git.

`codex-natural-chess-20260719T062119Z` is the full-media acceptance rollout on
the replacement source. It used the benchmark instruction with only local path
substitution, scored `0.0379`, and naturally took 237 completed shell calls.

`codex-replacement-chess-20260719T051110Z` is retained as a separate diagnostic.
It scored `0.0250` in 142 completed shell calls, but its local prompt explicitly
required at least 51 substantive calls and therefore does not supply the
natural-prompt evidence.

`claude-natural-chess-20260719T070702Z` is a fresh natural-prompt Claude Sonnet 5
attempt on the replacement source. It reached 210 completed tool uses naturally
but hit Claude's subscription session limit after 40 minutes 50 seconds, before
writing a solution. Its missing submission scored `0.0`; retain it as incomplete
failure evidence, not as the completed Claude cross-agent calibration. A
post-reset Claude rerun remains pending.

`antigravity-checkpoint-chess-20260719T162817Z` is a fresh replacement-source
Antigravity run with a canonical, path-rewritten initial prompt and externally
enforced checkpointing. The wrapper intervened at 45 and 51 completed tool
calls; Antigravity wrote and validated an 8-ply submission at 53 calls. It
scored `0.0205` and stopped below the 75-call cap. Because the rollout required
two checkpoint messages and installed packages from pip, retain it as completed
checkpoint-assisted diagnostic evidence rather than natural-prompt calibration.
