# Raw calibration trajectories

This directory contains exactly one full raw trajectory for each required
harness, plus the measured anti-shortcut runs listed in `../scores.md`.

- `codex-gpt-5.6-sol.jsonl`: complete native Codex CLI JSONL.
- `claude-opus-4.8-vscode-agent-sdk.jsonl`: complete maintainer-approved VS Code
  Claude Agent SDK AHP stream, treated as Claude Code-equivalent.
- `antigravity-gemini-3.6-flash-high.jsonl`: complete native Antigravity CLI
  stream-json trajectory. The final solution and response preceded a retained
  Vertex 429; a separately retained continuation repaired only the top-level
  schema wrapper, so this row requires manual audit.

Generated images, reward dumps, and model caches are not committed. Personal
home paths and task-specific calibration workspace roots are redacted; generic
temporary/cache paths may remain. Redaction replaces path strings only; no
events, tool inputs, tool results, or model messages are removed.
