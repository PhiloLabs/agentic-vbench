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
natural-prompt evidence. Fresh Claude and Antigravity replacement-source runs
remain pending.
