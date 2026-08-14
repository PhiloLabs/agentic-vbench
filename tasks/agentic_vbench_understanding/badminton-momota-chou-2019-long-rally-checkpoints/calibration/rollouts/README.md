# Rollouts

One raw trajectory per calibrated harness belongs here.

`codex-sol-xhigh.json` is the complete Codex-through-Harbor trajectory.

`gemini-35-flash-high.jsonl` is the raw Antigravity CLI event stream for the full
Gemini calibration. `gemini-35-flash-high-no-media.jsonl` is the raw event stream
for the no-media ablation.

`codex-sol-xhigh-single-frame.jsonl` and
`codex-sol-xhigh-frame-dump-no-tools.jsonl` are the raw Codex event streams for
the single-frame and all-frames/no-tools ablations.

`codex-sol-xhigh-video-only.jsonl` and `codex-sol-xhigh-audio-only.jsonl` are
the complete Codex CLI event streams for runs with physically isolated video
and audio streams. Local account names and unrelated parent-worktree status
output are redacted.

`claude-opus48-high.json` is the complete checkpointed Claude Code trajectory in
ATIF-v1.5. It retains all text, tool calls, tool results, rate-limit events, resume
boundaries, and final answers. Repeated transport fields are removed; embedded images
are deduplicated and resized, with original hashes and dimensions recorded in the
trajectory metadata.
