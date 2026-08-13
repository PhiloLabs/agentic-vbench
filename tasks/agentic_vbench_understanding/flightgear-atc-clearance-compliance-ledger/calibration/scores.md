# Calibration — FlightGear ATC clearance compliance ledger

The main reward is `0.9 * exact_leg_accuracy + 0.1 * clearance_chain_f1`
across five independent 13-clearance legs.

## Submission status

All three rows clear the measured difficulty gate. The maintainer
approved the VS Code Claude Agent SDK session as equivalent to Claude Code for
this contribution. The Antigravity row requires manual audit because Agent
Platform returned late errors and its 65-item array needed a schema-only wrapper.

## Required agent calibration

| harness | harness version | model | reasoning | score | tool-call turns | trajectory |
|---|---|---|---|---:|---:|---|
| Codex CLI | 0.147.0 | GPT-5.6 Sol | high | 0.000000 | 88 | `rollouts/codex-gpt-5.6-sol.jsonl` |
| VS Code Claude Agent SDK | Copilot Chat 0.60.0 | Claude Opus 4.8 | high | 0.010800 | 119 | `rollouts/claude-opus-4.8-vscode-agent-sdk.jsonl` |
| Antigravity CLI | 1.1.12 | Gemini 3.6 Flash High | high | 0.000000 | 89 | `rollouts/antigravity-gemini-3.6-flash-high.jsonl` |

Both accepted solutions contain all 65 chronological clearances and pass the
strict output validator. The Codex solver ended with `turn.completed`; wrapper
post-processing was reconstructed from the immutable trajectory, validated
solution, and 63 successful provider receipts. The Claude run is a fresh
`isResume=false` session, uses the frozen task container with `--network none`,
contains no subagent calls, and has no forbidden-path or network attempts.

The Antigravity run produced all 65 clearances and passed runtime isolation. Its
complete 282-event native trajectory retains a terminal Vertex
`RESOURCE_EXHAUSTED` error that followed the final solution and response. The
original output was a 65-item array rather than the required `clearances` object;
a narrow continuation added only that wrapper. Canonical comparison proved every
clearance and inner value unchanged. The continuation response was followed by
an Agent Platform sandbox transport reset, retained for manual review.

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
