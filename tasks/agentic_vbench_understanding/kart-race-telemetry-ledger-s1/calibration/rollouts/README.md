# Raw rollouts: one full trajectory per harness.

- `codex_ts_*` — **shipped** time-anchored run (reward **0.0892**, 12 races matched to their video
  windows). This is the strong-agent number in `SPEC.md`.
- `codex_3dim_*` — earlier completed 542-call run re-scored under the 3-dim metric with **no** time
  window (0.0236); `codex_exact_full_*` is that run's raw 4-quantity submission.

**Calibration history on HF** (agent narration + this rollout, secret-free — encrypted reasoning,
tool I/O and all environment/credentials stripped at extraction and re-scanned for keys, 0 hits):

<https://huggingface.co/datasets/explcre/agenticvbench-understanding-materials/tree/main/kart-race-telemetry-ledger-s1/calibration>

Agent: Codex CLI `gpt-5.6-sol`, `model_reasoning_effort=xhigh`, run locally (ChatGPT login).
