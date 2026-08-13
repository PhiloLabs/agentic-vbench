# Calibration — FlightGear ATC clearance compliance ledger

The main reward is `0.9 * exact_leg_accuracy + 0.1 * clearance_chain_f1`
across five independent 13-clearance legs.

## Submission status

All three rows clear the measured difficulty gate.

## Required agent calibration

| harness | harness version | model | reasoning | score | tool-call turns | trajectory |
|---|---|---|---|---:|---:|---|
| Codex CLI | 0.147.0 | GPT-5.6 Sol | high | 0.000000 | 88 | `rollouts/codex-gpt-5.6-sol.jsonl` |
| VS Code Claude Agent SDK | 0.60.0 | Claude Opus 4.8 | high | 0.010800 | 119 | `rollouts/claude-opus-4.8.jsonl` |
| Antigravity CLI | 1.1.12 | Gemini 3.6 Flash High | high | 0.000000 | 89 | `rollouts/antigravity-gemini-3.6-flash-high.jsonl` |

## Anchors and anti-shortcut runs

| run | reward | clearance-chain F1 | strict clearances | tool calls |
|---|---:|---:|---:|---:|
| oracle | 1.0000 | 1.0000 | 65/65 | — |
| empty/null | 0.0000 | 0.0000 | 0/65 | — |
| scripted ASR-only upper bound | 0.0000 | 0.0000 | 0/65 | — |
| no media | 0.0000 | 0.0000 | 0/65 | 9 |
| one frame | 0.0000 | 0.0000 | 0/65 | 9 |
| video only | 0.0000 | 0.0000 | 0/65 | 65 |
| audio only | 0.0031 | 0.0308 | 2/65 | 28 |
| frame dump + transcript, no media tools | 0.0000 | 0.0000 | 0/65 | 1 |

All reported numbers come from actual scored outputs. Failed intermediate design
rounds and replaced fixed-harness trajectories remain outside the PR under the
managed research Run; they are not presented as required-agent calibration.
