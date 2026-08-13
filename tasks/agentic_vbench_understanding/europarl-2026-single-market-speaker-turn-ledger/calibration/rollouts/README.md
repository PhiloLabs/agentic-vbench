# Raw calibration trajectories

Keep one complete raw trajectory per required agent and degraded-input run. Each
trajectory must include all tool calls and the final answer; summaries are not
acceptable calibration evidence.

- `codex-gpt-5.6-sol.jsonl`: complete native Codex CLI JSONL.
- `claude-opus-4.8-vscode-agent-sdk.jsonl`: complete maintainer-approved VS Code
  Claude Agent SDK AHP stream, treated as Claude Code-equivalent.
- `antigravity-gemini-3.6-flash-high.jsonl`: complete native Antigravity CLI
  stream-json trajectory. The final solution and response were produced before
  a retained Vertex 429 terminal error, so this row requires manual audit.

The other retained JSONL files are measured degraded-input audit trajectories.
They are not substitutes for the required full-agent raw streams above. Scores
and verifier outcomes are recorded once in `../scores.md`; duplicate reward,
solution, manifest, proxy, and summary sidecars are intentionally omitted.

Personal home paths and task-specific calibration workspace roots are
deterministically redacted. Redaction replaces path strings only; no events,
tool inputs, tool results, or model messages are removed.
