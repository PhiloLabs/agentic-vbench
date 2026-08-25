# Calibration - melee-nouns-bowl-2025-combo-kill-causal-ledger

The deterministic verifier reports **exact event-level F1** only. A predicted
event receives credit only when all six fields match one ground-truth event under
order-preserving one-to-one matching. Only exact event-level F1 is reported.

## Clean calibration

| harness | harness version | model | reasoning | exact F1 | predicted | schema-valid | exact matches | tool-call turns | trajectory |
|---|---|---|---|---:|---:|---:|---:|---:|---|
| Codex | `0.147.0-alpha.6.5` | `gpt-5.6-sol` | high | `0.0132` | 47 | 47 | 1 | 72 | `jobs/melee-codex-full-baseline-local-media-r3/melee-normal__VmESmXy/steps/solve/agent/trajectory.json` |
| Claude | `2.1.209` | `claude-sonnet-5` | not recorded | `0.0000` | 279 | 0 | 0 | 83 | `calibration/rollouts/claude-code.jsonl` |
| Antigravity | `Antigravity.app 2.3.1` | `Gemini 3.5 Flash` | not recorded | `0.0169` | 14 | 12 | 1 | 90 | `calibration/rollouts/antigravity.jsonl` |

The Codex row is the completed Full baseline r3 Harbor trial and is the Codex
clean calibration. The retained Claude and Antigravity exports are also clean
calibration rows for this submission.

## Scorer diagnostics

The ground-truth ledger contains 104 events. The exact-F1 values above correspond
to the following precision and recall diagnostics:

| harness | ground truth | predicted | schema-valid | exact matches | precision | recall | exact F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Codex | 104 | 47 | 47 | 1 | `0.0213` | `0.0096` | `0.0132` |
| Claude | 104 | 279 | 0 | 0 | `0.0000` | `0.0000` | `0.0000` |
| Antigravity | 104 | 14 | 12 | 1 | `0.0714` | `0.0096` | `0.0169` |

Claude used `P1` for every attacker instead of the closed player-tag vocabulary,
so the verifier found zero schema-valid entries. The exact-F1 result remains
included as the reported Claude clean-calibration score.

## Execution environment

| item | value |
|---|---|
| host OS | macOS `15.7.4` (Build `24G517`) |
| host hardware | MacBook Pro `Mac16,7`, Apple M4 Pro, 14 cores, 24 GB RAM |
| Codex execution | Harbor `0.20.0`, Docker `29.5.2` (`linux/arm64`) |
| Codex API route | `https://tokken.cc/v1` (credential omitted) |
| Claude execution | retained local Claude app/agent export on the same host; app version `2.1.209` |
| Antigravity execution | retained local Antigravity.app export on the same host; `Antigravity.app 2.3.1` |
| Python | `3.9.6` on the host |

No machine serial number, UUID, or credential is part of the calibration record.

## Codex ablations

All four recorded Codex ablations use exact F1 as the sole score:

| condition | run | exact F1 |
|---|---|---:|
| OCR-only | `melee-codex-ocr-only-ablation-20260825-r2` | `0.0000` |
| Single-frame | `melee-codex-single-frame-ablation-20260825-r3` | `0.0000` |
| No-media | `melee-no-media-20260825-r3` | `0.0000` |
| All-frames/no-tools | `melee-allframes-notools-20260825-r7` | `0.0000` |

Video-only is the full task input because the selected representation has no
audio; audio-only is not applicable.

## Qualification

Each retained clean-calibration harness is below the exact-F1 difficulty gate of
`0.10`, and each auditable trajectory contains more than 50 tool-call turns.
