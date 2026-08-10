# Calibration — FlightGear ATC clearance compliance ledger

The main reward is `0.9 * exact_leg_accuracy + 0.1 * clearance_chain_f1`
across five independent 13-clearance legs.

## Full-media model-family runs

The contributor explicitly requested GitHub Copilot subscription runs for all
three model families. These are measured Copilot CLI trajectories, **not**
vendor-native Codex CLI, Claude Code, or Antigravity runs. This is a documented
deviation from the repository's preferred harness matrix and remains reviewer
visible.

| harness | version | model | reasoning | reward | clearance-chain F1 | strict clearances | tool calls | raw trajectory |
|---|---|---|---|---:|---:|---:|---:|---|
| GitHub Copilot CLI | 1.0.79-9 | GPT-5.6 Sol | high | 0.0415 | 0.4154 | 27/65 | 60 | `rollouts/gpt-5.6-sol_copilot.jsonl` |
| GitHub Copilot CLI | 1.0.79-9 | Claude Opus 4.8 | high | 0.0046 | 0.0462 | 3/65 | 159 | `rollouts/claude-opus-4.8_copilot.jsonl` |
| GitHub Copilot CLI | 1.0.79-9 | Gemini 3.5 Flash | high | 0.0015 | 0.0154 | 1/65 | 116 | `rollouts/gemini-3.5-flash_copilot.jsonl` |

Every model reconstructed zero complete legs. The nonzero rewards above are the
10% clearance-F1 diagnostic component. The longest run used 159 genuine tool
calls; the shortest used 60.

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

All reported numbers come from actual scored outputs. Failed intermediate
design rounds and their trajectories are preserved durably outside the PR
under the managed research Run; they were not used as final calibration.
