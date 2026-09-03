# Rollouts

`codex-gpt-5.6-sol-v1.jsonl` is the formal Codex CLI 0.144.4 / GPT-5.6 Sol run
against the hardened schema. It made 87 tool calls and scored 0.0.

`claude-opus-4.8-hardened-v1.jsonl` is the formal Claude Code 2.1.220 / Opus 4.8
run. The five contiguous segments made 411 tool calls and scored 0.0. To keep the
trajectory below hosting limits, embedded base64 image payloads are replaced with
their byte counts and SHA256 hashes; messages, tool calls, paths, and results are
otherwise retained.

`claude-fable-5-access-blocked.jsonl` records the requested Fable 5 launch. The
provider returned HTTP 403 before inference, so it is not a scored run.

`gemini-cli-3.5-flash-hardened-v1.jsonl` is the Gemini CLI at Meta 0.51.0 /
Gemini 3.5 Flash fallback run. Its three contiguous segments made 91 tool calls,
predicted 16 events, and scored 0.0.

`gemini-cli-3.1-pro-preview-hardened-v1.jsonl` is the corresponding Gemini 3.1
Pro Preview fallback run. Its three contiguous segments made 56 tool calls,
predicted seven events, and scored 0.0.

Native Antigravity `agy` was unavailable for the Gemini runs. A local policy denied
web, MCP, package installation, Swift/Vision, and outside-directory access. Gemini
CLI may record `gemini-3-flash-preview` as an internal media helper; each segment's
`init` event records the requested main model.

Host paths in the committed copies are redacted from `/Users/<name>` to
`/home/calibrator`. This is the only textual sanitization beyond the documented
Claude image-payload replacement.
