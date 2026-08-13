# Raw calibration trajectories

Keep one complete raw trajectory per required agent. Each trajectory includes
all tool calls and the final answer.

- `codex-gpt-5.6-sol.jsonl`: complete native Codex CLI JSONL.
- `claude-opus-4.8.jsonl`: complete VS Code Claude Agent SDK
  AHP stream.
- `antigravity-gemini-3.6-flash-high.jsonl`: complete native Antigravity CLI
  stream-json trajectory.

Degraded-input scores and verifier outcomes are recorded in `../scores.md`.

Personal home paths and task-specific calibration workspace roots are
deterministically redacted. Redaction replaces path strings only; no events,
tool inputs, tool results, or model messages are removed.
