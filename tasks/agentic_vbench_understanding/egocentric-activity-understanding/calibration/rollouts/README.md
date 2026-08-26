# Raw calibration trajectories

Empty until the task is calibrated. Keep one complete raw trajectory per required
agent (Antigravity, Codex CLI, Claude Code CLI), including every tool call and the
final answer — summaries cannot be audited.

Expected filenames, matching the table in `../scores.md`:

- `codex-gpt-5.6-sol.jsonl` — native Codex CLI JSONL
- `claude-opus-4.8.jsonl` — Claude Code CLI stream-json
- `antigravity-gemini-3.6-flash-high.jsonl` — native Antigravity CLI stream-json;
  primary invalid early-exit attempt
- `antigravity-gemini-3.6-flash-high.retry1.jsonl` — identical retry that reproduced
  the early exit

Redact personal home paths deterministically, replacing path strings only; do not
drop events, tool inputs, tool results, or model messages. Do not commit `reward.json`
dumps or binaries here — scores belong in `../scores.md`.
