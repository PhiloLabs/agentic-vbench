# Rollouts

- `claude-code-fable.jsonl` — Claude Code CLI (Fable 5), fresh run on the fixed task
  (rectified-frame ground truth, visible queries, hand_model.json shipped) under the
  shipped configuration: inside the built task image, network restricted to the model
  endpoint by a DNS allowlist gate (pip installs and lookups fail as with
  allow_internet=false), 60 minute budget, shipped tools only. Ends with the CLI's
  closing result record. This is the run behind the calibration row in `../scores.md`.
- `claude-code-fable-opennet.jsonl` — the earlier Fable 5 run on the pre-fix task
  (native-frame GT), network open; kept for the record.
- `claude-code.jsonl` — Claude Code CLI (Opus 4.8) on the pre-fix task.
- `codex.txt` — Codex CLI (GPT-5.5) on the pre-fix task.
- `antigravity.txt` — Antigravity CLI (Gemini 3.5 Flash) on the pre-fix task.
- `cursor.jsonl` — Cursor CLI (Composer) on the pre-fix task.

Base64 image payloads in the in-repo copies are elided to keep the repo small; complete
versions of every retained trajectory, frames included, live in the immutable archive
listed in `../scores.md` with per-file SHA256.
