# Calibration - robocup-2024-final-possession-chain-ledger

Deterministic event-level F1 scorer: `steps/solve/tests/judge.py`.

| harness | harness version | model | reasoning | score | tool-call turns | trajectory |
|---|---|---|---|---:|---:|---|
| Oracle | local | answer key | n/a | 1.0 | n/a | n/a |
| Empty output | local | n/a | n/a | 0.0 | n/a | n/a |
| Codex Desktop | 0.144.2 | `gpt-5.6-sol` | high | 0.0 | 163 | `rollouts/codex.jsonl` |
| Claude local agent | 2.1.209 | `claude-sonnet-5` | not recorded | 0.0385 | 46 | `rollouts/claude-code.jsonl` |
| Antigravity | not recorded | not recorded | not recorded | 0.0 | 176 | `rollouts/antigravity.jsonl` |

## Scorer diagnostics

| harness | GT chains | predicted | schema-valid | exact matches | core matches |
|---|---:|---:|---:|---:|---:|
| Codex Desktop | 17 | 1 | 1 | 0 | 1 |
| Claude local agent | 17 | 35 | 35 | 1 | 5 |
| Antigravity | 17 | 33 | 0 | 0 | 0 |

The Antigravity output omitted the required `half` field from every chain, making
all 33 predictions schema-invalid. The Claude output produced the only exact chain
match. All three reported rewards are below 0.10, and the Codex and Antigravity
attempts each exceed 50 tool calls.

## Tool-call counting

- Codex: 150 `custom_tool_call` records plus 13 `function_call` records.
- Claude: 46 assistant `tool_use` content blocks.
- Antigravity: 176 entries in `PLANNER_RESPONSE.tool_calls`.

## Calibration status

These are the final reported agent results for this submission. They were performed
in local desktop/local-agent workspaces rather than through the shipped Harbor
image. No Harbor rerun is claimed.

Single-frame, no-media, OCR-only, and all-frames/no-tools ablations were not measured
for this submission. Video-only is the full task input because the selected
representation has no audio; audio-only is not applicable.
