# Calibration — europarl-2026-single-market-speaker-turn-ledger

The frozen verifier uses monotonic one-to-one event F1. A true positive requires
exact anonymous identity, exact floor-language code, exact semantic-card ID, and
both handover boundaries within 3.5 seconds.

Measured anchors: oracle `1.000000`; empty/null submission `0.000000`.

## Submission status

All three rows clear the measured difficulty gate.

## Required agent calibration

| harness | harness version | model | reasoning | score | tool-call turns | trajectory |
|---|---|---|---|---:|---:|---|
| Codex CLI | 0.147.0 | GPT-5.6 Sol | xhigh | 0.034884 | 184 | `rollouts/codex-gpt-5.6-sol.jsonl` |
| VS Code Claude Agent SDK | 0.60.0 | Claude Opus 4.8 | high | 0.023256 | 110 | `rollouts/claude-opus-4.8.jsonl` |
| Antigravity CLI | 1.1.12 | Gemini 3.6 Flash High | high | 0.000000 | 367 | `rollouts/antigravity-gemini-3.6-flash-high.jsonl` |

## Required anti-shortcut runs

All rows below are fresh runs on the frozen inferential-card package. Pre-redesign
scores are excluded.

| degraded input | score | outcome |
|---|---:|---|
| no media | 0.000000 | agent declined to submit |
| single frame | 0.000000 | submitted empty turns |
| video only | 0.000000 | submitted 76 turns |
| audio only | 0.000000 | agent declined to submit |
| all 1 fps frames pasted, no tools | 0.000000 | submitted 86 turns |
