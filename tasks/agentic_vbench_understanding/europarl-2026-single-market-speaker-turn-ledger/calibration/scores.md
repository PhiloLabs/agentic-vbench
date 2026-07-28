# Calibration — europarl-2026-single-market-speaker-turn-ledger

The frozen verifier uses monotonic one-to-one event F1. A true positive requires
exact anonymous identity, exact floor-language code, exact semantic-card ID, and
both handover boundaries within 3.5 seconds.

Copilot runs execute inside image
`sha256:fa81b0532ba0eafd31e1ad1cf15e3ad15b95317be1d691c93bbea93927e472fb`.
Web/MCP tools and custom instructions are disabled. An internal Docker network
blocks direct egress; a host CONNECT proxy permits `api.github.com` only during
CLI token validation, permanently revokes it when the first Copilot model
connection begins, and thereafter permits only Copilot API endpoints. Curl/pip
are also disabled.
The local harness is disclosed rather than described as native Codex, Claude Code,
or Gemini CLI. Every run enforces the shipped 4-CPU, 8-GB memory, 14,400-second
agent envelope and uses a fresh empty artifact mount.

| harness | model | reasoning | score | tool calls | trajectory |
|---|---|---|---:|---:|---|
| Stock Harbor 0.6.6 | exact oracle | — | 1.000000 | — | job `1785273826` |
| deterministic | empty turns | — | 0.000000 | — | `rollouts/empty.reward.json` |
| GitHub Copilot CLI 1.0.76-0 | GPT-5.6 Sol | xhigh | 0.023392 | 231 | `rollouts/gpt-5.6-sol_copilot.audit.jsonl` ([raw](https://huggingface.co/datasets/Jordan8717/agentic-vbench-europarl/resolve/ea0cfe009016f3060f1d9a10c6cef55eae86bec8/calibration-inferential-final-v3/gpt-5.6-sol_copilot.jsonl)) |
| GitHub Copilot CLI 1.0.76-0 | Claude Opus 5 | xhigh | 0.116279 | 317 | `rollouts/claude-opus-5_copilot.audit.jsonl` ([raw](https://huggingface.co/datasets/Jordan8717/agentic-vbench-europarl/resolve/ea0cfe009016f3060f1d9a10c6cef55eae86bec8/calibration-inferential-final-v3/claude-opus-5_copilot.jsonl)) |
| GitHub Copilot CLI 1.0.76-0 | Gemini 3.5 Flash | xhigh | 0.000000 | 205 | `rollouts/gemini-3.5-flash_copilot.audit.jsonl` ([raw](https://huggingface.co/datasets/Jordan8717/agentic-vbench-europarl/resolve/ea0cfe009016f3060f1d9a10c6cef55eae86bec8/calibration-inferential-final-v3/gemini-3.5-flash_copilot.jsonl)) |

Gemini's provider accepts at most ten images in one conversation. Its disclosed
runtime prefix required labeled contact sheets, no more than ten image views, no
process-killing, and an explicit saved solution. The task prompt itself was
unchanged. This result is **provider-limited and not directly comparable** to the
other two full-model rows.

Opus made one explicit connectivity probe; it failed. The sealed proxy recorded
no allowed public destination. See
`rollouts/claude-opus-5_copilot.manual-audit.json`.

Opus's `0.116279` exceeds the nominal `< 0.10` README target. It is reported
without smoothing: 10/86 exact turns, exact 95% binomial CI `[0.057, 0.204]`;
under `p=0.10`, `P(TP >= 10)=0.357`. GPT-5.6 is the designated first calibration
model and passes the checker at `0.023392`; maintainer adjudication is requested
for the singular-versus-plural README wording.

## Required anti-shortcut runs

All rows below are fresh runs on the frozen inferential-card package. Pre-redesign
scores are excluded.

| degraded input | model / harness | score | outcome | trajectory |
|---|---|---:|---|---|
| no media | GPT-5.6 Sol / GitHub Copilot CLI 1.0.76-0 | 0.000000 | agent declined to submit | `rollouts/ablation-no-media.audit.jsonl` ([raw](https://huggingface.co/datasets/Jordan8717/agentic-vbench-europarl/resolve/ea0cfe009016f3060f1d9a10c6cef55eae86bec8/calibration-inferential-final-v3/ablation-no-media.jsonl)) |
| single frame | GPT-5.6 Sol / GitHub Copilot CLI 1.0.76-0 | 0.000000 | submitted empty turns | `rollouts/ablation-single-frame.audit.jsonl` ([raw](https://huggingface.co/datasets/Jordan8717/agentic-vbench-europarl/resolve/ea0cfe009016f3060f1d9a10c6cef55eae86bec8/calibration-inferential-final-v3/ablation-single-frame.jsonl)) |
| video only | GPT-5.6 Sol / GitHub Copilot CLI 1.0.76-0 | 0.000000 | submitted 76 turns | `rollouts/ablation-video-only.audit.jsonl` ([raw](https://huggingface.co/datasets/Jordan8717/agentic-vbench-europarl/resolve/ea0cfe009016f3060f1d9a10c6cef55eae86bec8/calibration-inferential-final-v3/ablation-video-only.jsonl)) |
| audio only | GPT-5.6 Sol / GitHub Copilot CLI 1.0.76-0 | 0.000000 | agent declined to submit | `rollouts/ablation-audio-only.audit.jsonl` ([raw](https://huggingface.co/datasets/Jordan8717/agentic-vbench-europarl/resolve/ea0cfe009016f3060f1d9a10c6cef55eae86bec8/calibration-inferential-final-v3/ablation-audio-only.jsonl)) |
| all 1 fps frames pasted, no tools | GPT-5.6 Sol / GitHub Copilot CLI 1.0.76-0 | 0.000000 | submitted 86 turns | `rollouts/ablation-frame-dump-no-tools.audit.jsonl` ([raw](https://huggingface.co/datasets/Jordan8717/agentic-vbench-europarl/resolve/ea0cfe009016f3060f1d9a10c6cef55eae86bec8/calibration-inferential-final-v3/ablation-frame-dump-no-tools.jsonl)) |
