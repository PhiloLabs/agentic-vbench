# Rollouts

- `claude-code-fable.jsonl` — Claude Code CLI (Fable 5), fresh complete run on the fixed
  task (rectified-frame ground truth, target-visible queries) under the shipped
  configuration: inside the built task image, network restricted to the model endpoint
  by a DNS allowlist gate (pip installs and lookups fail as with allow_internet=false),
  60 minute budget, shipped tools only. Ends with the CLI's closing result record. This
  is the run behind the calibration row in `../scores.md`.
- `claude-code-fable-opennet.jsonl` — the earlier Fable 5 run (object_points shipped,
  native-frame GT, network open, 98 minutes); kept for the record.
- `codex.txt` — Codex CLI (GPT-5.5) on the revision before object_points shipped.
- `cursor.jsonl` — Cursor CLI (Composer) on the same earlier revision.
- `antigravity.txt` — Antigravity CLI (Gemini 3.5 Flash) on the same earlier revision,
  in a filesystem-isolated container; it produced no solution.json.

Base64 image payloads in the in-repo copies are elided to keep the repo small; complete
versions of every retained trajectory, frames included, live in the immutable archive
listed in `../scores.md` with per-file SHA256. Ablation runs are under `../ablations/`.
