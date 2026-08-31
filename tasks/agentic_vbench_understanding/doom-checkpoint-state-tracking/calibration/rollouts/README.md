# Calibration rollouts

One plain-text trajectory is retained for each reported harness run:

- `antigravity.jsonl`
- `codex.jsonl`
- `claude-code.jsonl`

Every source harness event remains in its original order. Embedded image bodies
are replaced by explicit text markers; tool calls, text outputs, and model messages
are retained. Sizes and SHA256 digests are recorded in `../scores.md`.
