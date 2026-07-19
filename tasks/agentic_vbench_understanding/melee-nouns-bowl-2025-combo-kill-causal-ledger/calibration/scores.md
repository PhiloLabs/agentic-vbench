# Calibration - melee-nouns-bowl-2025-combo-kill-causal-ledger

Deterministic event-level F1 scorer: `steps/solve/tests/judge.py`.

| harness | harness version | model | reasoning | score | tool-call turns | trajectory |
|---|---|---|---|---:|---:|---|
| Oracle | local | answer key | n/a | 1.0 | n/a | n/a |
| Empty output | local | n/a | n/a | 0.0 | n/a | n/a |
| Codex Desktop | 0.144.2 | `gpt-5.6-sol` | high | 0.0899 | 145 | `rollouts/codex.jsonl` |
| Claude local agent | 2.1.209 | `claude-sonnet-5` | not recorded | 0.0 | 83 | `rollouts/claude-code.jsonl` |
| Antigravity | not recorded | not recorded | not recorded | 0.0169 | 90 | `rollouts/antigravity.jsonl` |

## Scorer diagnostics

| harness | GT events | predicted | schema-valid | exact matches | core matches |
|---|---:|---:|---:|---:|---:|
| Codex Desktop | 104 | 74 | 74 | 8 | 47 |
| Claude local agent | 104 | 279 | 0 | 0 | 0 |
| Antigravity | 104 | 14 | 12 | 1 | 11 |

The Claude output used `P1` for every attacker instead of the closed player-tag
vocabulary, so all 279 predictions were schema-invalid. The scorer still includes
them in the precision denominator, as specified by the formal verifier.

## Tool-call counting

- Codex: 125 `custom_tool_call` records plus 20 `function_call` records.
- Claude: 83 assistant `tool_use` content blocks.
- Antigravity: 90 entries in `PLANNER_RESPONSE.tool_calls`.

## Calibration status

All three retained outputs score below 0.10 and every auditable call count exceeds
50. These are the final reported agent results for this submission. They were
performed in local desktop/local-agent workspaces rather than through the shipped
Harbor image. The Antigravity export does not record its model or harness version.
No Harbor rerun is claimed.

Single-frame, no-media, OCR-only, and all-frames/no-tools ablations were not measured
for this submission. Video-only is the full task input because the selected
representation has no audio; audio-only is not applicable.
