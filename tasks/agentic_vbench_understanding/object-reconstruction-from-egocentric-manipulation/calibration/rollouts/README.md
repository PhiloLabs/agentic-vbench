# Rollouts

One raw agent transcript per agent, so a reviewer can confirm the score was earned
honestly and count the tool-call turns:

- `claude-code-fable.jsonl` — Claude Code CLI (Fable 5), fresh run on the shipped task,
  executed inside the built task image (only the baked materials were reachable); ends
  with the CLI's closing result record
- `claude-code.jsonl` — Claude Code CLI (Opus 4.8), stream-json transcript
- `codex.txt` — Codex CLI transcript (codex exec prints a plain-text log, not JSONL)
- `antigravity.txt` — Antigravity CLI transcript (run in a filesystem-isolated Docker
  container that mounts only `materials/`, so it cannot reach the repo or any other run)
- `cursor.jsonl` — Cursor CLI transcript

Each transcript shows the full run (all tool calls plus the final deliverable). The agent
is given only `materials/` (the three clips plus the camera and object-name metadata);
the reference meshes and ground truth are never staged into its workspace.

Note: base64 image payloads in the transcripts (frames the agent sampled) are elided
(`"<elided base64>"`) to keep file sizes reasonable; all tool calls, reasoning, and the
final answer are intact.
