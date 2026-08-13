# Calibration — FlightGear ATC clearance compliance ledger

The main reward is `0.9 * exact_leg_accuracy + 0.1 * clearance_chain_f1`
across five independent 13-clearance legs.

## Submission status

All three rows clear the measured difficulty gate.

## Required agent calibration

| harness | harness version | model | reasoning | score | tool-call turns | trajectory |
|---|---|---|---|---:|---:|---|
| Codex CLI | 0.147.0 | GPT-5.6 Sol | high | 0.000000 | 88 | `rollouts/codex-gpt-5.6-sol.jsonl` |
| VS Code Claude Agent SDK | Copilot Chat 0.60.0 | Claude Opus 4.8 | high | 0.010800 | 119 | `rollouts/claude-opus-4.8-vscode-agent-sdk.jsonl` |
| Antigravity CLI | 1.1.12 | Gemini 3.6 Flash High | high | 0.000000 | 89 | `rollouts/antigravity-gemini-3.6-flash-high.jsonl` |

## Anchors and anti-shortcut runs

| run | reward | clearance-chain F1 | strict clearances | tool calls | trajectory |
|---|---:|---:|---:|---:|---|
| oracle | 1.0000 | 1.0000 | 65/65 | — | Harbor oracle job |
| empty/null | 0.0000 | 0.0000 | 0/65 | — | deterministic |
| scripted ASR-only upper bound | 0.0000 | 0.0000 | 0/65 | — | deterministic |
| no media, GPT-5.6 Sol | 0.0000 | 0.0000 | 0/65 | 9 | `ablations/no-media_gpt-5.6-sol_copilot.jsonl` |
| one frame, GPT-5.6 Sol | 0.0000 | 0.0000 | 0/65 | 9 | `ablations/single-frame_gpt-5.6-sol_copilot.jsonl` |
| video only, GPT-5.6 Sol | 0.0000 | 0.0000 | 0/65 | 65 | `ablations/video-only_gpt-5.6-sol_copilot.jsonl` |
| audio only, GPT-5.6 Sol | 0.0031 | 0.0308 | 2/65 | 28 | `ablations/audio-only_gpt-5.6-sol_copilot.jsonl` |
| frame dump + transcript, no media tools, GPT-5.6 Sol | 0.0000 | 0.0000 | 0/65 | 1 | `ablations/frame-dump-no-tools_gpt-5.6-sol_copilot.jsonl` |

All reported numbers come from actual scored outputs. Failed intermediate design
rounds and replaced fixed-harness trajectories remain outside the PR under the
managed research Run; they are not presented as required-agent calibration.
