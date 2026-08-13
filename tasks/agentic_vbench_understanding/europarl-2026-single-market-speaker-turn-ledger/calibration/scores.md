# Calibration — europarl-2026-single-market-speaker-turn-ledger

The frozen verifier uses monotonic one-to-one event F1. A true positive requires
exact anonymous identity, exact floor-language code, exact semantic-card ID, and
both handover boundaries within 3.5 seconds.

Measured anchors: oracle `1.000000`; empty/null submission `0.000000`.

## Submission status

All three rows clear the measured difficulty gate. The maintainer
approved the VS Code Claude Agent SDK session as equivalent to Claude Code for
this contribution. The Antigravity row requires manual audit because Agent
Platform returned a late 429 after producing the final solution and response.

## Required agent calibration

| harness | harness version | model | reasoning | score | tool-call turns | trajectory |
|---|---|---|---|---:|---:|---|
| Codex CLI | 0.147.0 | GPT-5.6 Sol | xhigh | 0.034884 | 184 | `rollouts/codex-gpt-5.6-sol.jsonl` |
| VS Code Claude Agent SDK | Copilot Chat 0.60.0 | Claude Opus 4.8 | high | 0.023256 | 110 | `rollouts/claude-opus-4.8-vscode-agent-sdk.jsonl` |
| Antigravity CLI | 1.1.12 | Gemini 3.6 Flash High | high | 0.000000 | 367 | `rollouts/antigravity-gemini-3.6-flash-high.jsonl` |

Both accepted solutions contain 86 valid chronological turns. The Codex solver
ended with `turn.completed`; wrapper post-processing was reconstructed from the
immutable trajectory, validated solution, empty stderr, and 412 successful
provider receipts. Two attempted GitHub model downloads failed under blocked DNS
and returned no external bytes. Five `/harness-home` searches found no model,
history, token, or usable cache. This is retained as a manual-audit disclosure,
not hidden from reviewers.

The Claude run is a fresh `isResume=false` session, uses the frozen task container
with `--network none`, contains no subagent calls, and has no forbidden-path or
network access. Three nonblocking host Bash deviations only managed the named
container or parsed this row's final solution.

The Antigravity run produced 74 schema-valid chronological turns and passed
runtime isolation. Its complete 1,217-event native trajectory retains a terminal
Vertex `RESOURCE_EXHAUSTED` error that followed the final solution and response.
A narrow validation continuation confirmed the unchanged solution locally, but
its response was followed by an Agent Platform sandbox transport reset; both
errors remain in managed research artifacts and require manual review.

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
