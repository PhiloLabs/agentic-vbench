# Rollouts

This directory contains compact calibration artifacts for local strong-agent and
anti-shortcut rollouts.

The Codex, Claude, and Antigravity full-media runs predate the replacement source
and are retained only as historical review context. They do not count toward
acceptance for the current task material.

The replacement-source `single_frame` and `no_media` Codex ablations are recorded
here as compact rewards and run summaries. Their bulky local workspaces are kept
out of git.

`codex-replacement-chess-20260719T051110Z` is a fresh full-media Codex diagnostic
on the replacement source. It scored `0.0250` in 142 completed shell calls, but
its local prompt explicitly required at least 51 substantive calls. Keep it as
useful audit evidence; a benchmark-instruction-only Codex run is still required
for natural-prompt acceptance. Fresh Claude and Antigravity full-media runs also
remain pending.
