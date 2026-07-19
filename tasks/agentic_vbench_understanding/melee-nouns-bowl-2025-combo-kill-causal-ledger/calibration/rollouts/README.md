# Rollout records

One retained JSONL transcript is stored for each evaluated agent:

- `codex.jsonl`: Codex Desktop 0.144.2, `gpt-5.6-sol`, high reasoning.
- `claude-code.jsonl`: Claude local agent 2.1.209, `claude-sonnet-5`.
- `antigravity.jsonl`: Antigravity export; model and harness version were not
  recorded by the export.

The Antigravity file contains 90 explicit planner tool calls and is the final
Antigravity artifact reported by this submission.

The exports have three mechanical redactions. Original local home-directory prefixes
are replaced with `/home/agent`. The Codex export's 33 embedded base64 JPEG values are
replaced by placeholders containing the original value's SHA256 and character
count; this avoids committing 20 MB of binary payload and prevents false-positive
secret scanning. Its opaque encrypted-content blobs are replaced by the same kind of
SHA256/length placeholder because they cannot be reviewed and also resemble secrets.
Model messages, tool calls, textual tool results, and timestamps are otherwise
unchanged. Candidate output and reward dumps are intentionally not duplicated here;
measured verifier diagnostics are in `../scores.md`.
