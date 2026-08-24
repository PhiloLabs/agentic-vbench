# Calibration trajectories (in-repo audit record)

One secret-free trajectory per strong-agent row in `../scores.md`. Each keeps the agent's own
commentary and the shell commands it ran; tool outputs, encrypted reasoning, and all
environment/credential context were dropped at extraction and re-scanned for keys (0 hits).

- `codex_trajectory.md` — Codex CLI `gpt-5.6-sol` (xhigh), 241 tool calls (n=3 runs: 242/120/237).
- `claude_trajectory.md` — Claude Code CLI `claude-opus-4-8`, 108 tool calls.

**Rollout dumps (solution.json + reward.json) are on HF**, pinned to an immutable revision (not a
mutable `main` link), whole-file SHA256 recorded:

```
REV=39f1b933102acb3e52348752eb736b31c4c9d50b
base=https://huggingface.co/datasets/explcre/agenticvbench-understanding-materials/resolve/$REV/kart-race-telemetry-ledger-s1/calibration
```
- `$base/codex_solution.json`, `$base/codex_reward.json` (Codex run 3, the max of n=3)
- `$base/claude_solution.json`, `$base/claude_reward.json`
- trajectory copies also on HF; SHA256:
  - `codex_trajectory.md`  `91ad2adbf6cb17915c4af42ec22dd38edd5348a276404f581853e7eaf20cb609`
  - `claude_trajectory.md` `5feeb91ccbe04bf6435deab251419d8851e01a364ce4626128655ea913204cc0`
