# Calibration — europarl-2026-single-market-speaker-turn-ledger

The verifier uses monotonic one-to-one event F1. A true positive requires the exact
anonymous speaker ID and both boundaries within 4 seconds.

Exact verifier counts, statuses, trajectory hashes, and checker gates are recorded
in `results.json`. Official source hashes and the reproducible 170-to-86 record
constructor are recorded in `source_provenance.json` and `build_ground_truth.py`.
The independent integrity verdict is in `experiment_audit.md` and
`experiment_audit.json`.

Copilot runs execute as a non-root user inside the built task image. Web/MCP tools
and custom instructions are disabled. Raw tool commands are audited for URLs,
public lookup, and verifier paths before a score is accepted.

The available local harness exposes all three required model families through
GitHub Copilot CLI rather than separate vendor-native CLIs. Model IDs, harness
version, reasoning effort, full raw trajectories, and tool-call counts are reported
without relabeling the harness.

| harness | harness version | model | reasoning | score | tool-call turns | trajectory |
|---|---|---|---|---:|---:|---|
| Oracle | task oracle | exact answer | — | 1.000 | — | — |
| Empty / null | deterministic | empty turns | — | 0.000 | — | — |
| GitHub Copilot CLI | 1.0.75 | GPT-5.6 Sol | xhigh | 0.000 | 124 | `rollouts/gpt-5.6-sol_copilot.jsonl` |
| GitHub Copilot CLI | 1.0.75 | Claude Opus 5 | xhigh | 0.000 | 260 | `rollouts/claude-opus-5_copilot.jsonl` |
| GitHub Copilot CLI | 1.0.75 | Gemini 3.5 Flash | xhigh | 0.000 | 140 | `rollouts/gemini-3.5-flash_copilot.jsonl` |

## Required anti-shortcut runs

| degraded input | model / harness | score | trajectory |
|---|---|---:|---|
| no media | GPT-5.6 Sol / GitHub Copilot CLI 1.0.75 | 0.000 | [raw](https://huggingface.co/datasets/Jordan8717/agentic-vbench-europarl/resolve/bd3fda7e1de250c5452814a94b016f4de65b2195/calibration/ablation-no-media.jsonl) |
| single frame | GPT-5.6 Sol / GitHub Copilot CLI 1.0.75 | 0.000 | [raw](https://huggingface.co/datasets/Jordan8717/agentic-vbench-europarl/resolve/bd3fda7e1de250c5452814a94b016f4de65b2195/calibration/ablation-single-frame.jsonl) |
| video only | GPT-5.6 Sol / GitHub Copilot CLI 1.0.75 | 0.000 | [raw](https://huggingface.co/datasets/Jordan8717/agentic-vbench-europarl/resolve/bd3fda7e1de250c5452814a94b016f4de65b2195/calibration/ablation-video-only.jsonl) |
| audio only | GPT-5.6 Sol / GitHub Copilot CLI 1.0.75 | 0.000 | [raw](https://huggingface.co/datasets/Jordan8717/agentic-vbench-europarl/resolve/bd3fda7e1de250c5452814a94b016f4de65b2195/calibration/ablation-audio-only.jsonl) |
| all 1 fps frames pasted, no tools | GPT-5.6 Sol / GitHub Copilot CLI 1.0.75 | 0.012 | [raw](https://huggingface.co/datasets/Jordan8717/agentic-vbench-europarl/resolve/bd3fda7e1de250c5452814a94b016f4de65b2195/calibration/ablation-frame-dump-no-tools.jsonl) |

The video-only row is the primary modality check: the task claims that floor audio
is required to recover intervention boundaries rather than camera-cut boundaries.

All provided checks in `scripts/understanding/check_task.py` pass, including the
five ablation flags, pinned 127.7-minute 1080p input, oracle/null anchors, strong
agent threshold, and long-horizon tool-call threshold.
