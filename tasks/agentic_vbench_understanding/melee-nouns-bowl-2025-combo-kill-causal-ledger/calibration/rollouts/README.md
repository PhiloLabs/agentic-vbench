# Rollout records

Retained supplemental transcripts are stored for the evaluated agents:

- `codex.jsonl`: compact retained Codex export. The selected Full baseline r3 raw
  trajectory is the Harbor artifact at the path recorded in `../scores.md`.
- `claude-code.jsonl`: retained Claude calibration export, version 2.1.209,
  `claude-sonnet-5`.
- `antigravity.jsonl`: retained Antigravity calibration export, model `Gemini 3.5
  Flash`, harness `Antigravity.app 2.3.1`.

The Antigravity file contains 90 explicit planner tool calls and is the retained
Antigravity artifact reported by this submission. Exact-F1 diagnostics are in
`../scores.md`.

The exports have three mechanical redactions. Original local home-directory prefixes
are replaced with `/home/agent`. The Codex export's 33 embedded base64 JPEG values are
replaced by placeholders containing the original value's SHA256 and character
count; this avoids committing 20 MB of binary payload and prevents false-positive
secret scanning. Its opaque encrypted-content blobs are replaced by the same kind of
SHA256/length placeholder because they cannot be reviewed and also resemble secrets.
Model messages, tool calls, textual tool results, and timestamps are otherwise
unchanged. Candidate output and reward dumps are intentionally not duplicated here;
measured verifier diagnostics are in `../scores.md`.
