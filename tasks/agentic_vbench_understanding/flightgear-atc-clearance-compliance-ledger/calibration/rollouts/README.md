# Raw calibration trajectories

This directory contains exactly one full raw trajectory for each required
harness. Measured anti-shortcut results are listed in `../scores.md`.

- `codex-gpt-5.6-sol.jsonl`: complete native Codex CLI JSONL.
- `claude-opus-4.8.jsonl`: complete VS Code Claude Agent SDK
  AHP stream.
- `antigravity-gemini-3.6-flash-high.jsonl`: complete native Antigravity CLI
  stream-json trajectory.

Generated images, reward dumps, and model caches are not committed. Personal
home paths and task-specific calibration workspace roots are redacted; generic
temporary/cache paths may remain. Redaction replaces path strings only; no
events, tool inputs, tool results, or model messages are removed.
