# Calibration - robocup-2024-final-possession-chain-ledger

The final qualification pass must use the exact checked-in instruction, weighted-F1
verifier, task commit, and image built from the digest-pinned Dockerfile. Do not mix
results from earlier scorer or prompt revisions into this table.

## End-to-end agents

| harness | harness version | model | reasoning | score | predicted | tool-call turns | trajectory asset | whole-file SHA256 |
|---|---|---|---|---:|---:|---:|---|---|
| Oracle | pending clean pass | answer key | n/a | pending | pending | n/a | n/a | n/a |
| Empty output | pending clean pass | n/a | n/a | pending | 0 | n/a | n/a | n/a |
| Codex | pending clean pass | GPT-5.6 Sol | high | pending | pending | pending | pending | pending |
| Claude Code | pending clean pass | Fable 5 or Opus 4.8 | pending | pending | pending | pending | pending | pending |
| Gemini harness | pending clean pass | Gemini 3.1 Pro or 3.5 Flash | pending | pending | pending | pending | pending | pending |

## Anti-shortcut ablations

All four rows are real GPT-5.6 Sol runs under the final image and scorer. Exact input
conditions are fixed in `ablations/README.md`.

| condition | score | predicted | tool-call turns | trajectory asset | whole-file SHA256 |
|---|---:|---:|---:|---|---|
| Prompt/schema, no media | pending | pending | pending | pending | pending |
| One temporal-midpoint frame | pending | pending | pending | pending | pending |
| OCR-only timeline | pending | pending | pending | pending | pending |
| Every native frame pasted, no tools | pending | pending | 0 | pending | pending |

## Run identity

Record these once the final image is built and do not change the task between rows:

| item | value |
|---|---|
| task commit | pending |
| Harbor version | pending |
| image repository digest or local image ID | pending |
| base image digest | `python:3.12-slim@sha256:2c941e860699f878900b0edc2403613c234d4b32eda3cc9fa7036991a2a63c4a` |
| media SHA256 | `076bcc59fc48443d24a72a87162021470b9e645b41c858c3ffa5b5b25bae36cd` |

## Counting rules

For Harbor ATIF trajectories, count tool calls as the number of `tool_calls` objects
attached to agent-authored steps across the main trajectory and any explicitly
referenced subagent trajectories. Record any harness-native comparison count and its
record type separately when it differs. A run clears the difficulty gate only when
every strong agent scores below `0.10` and a genuine end-to-end attempt exceeds 50
tool-call turns. Every ablation must score at most `0.15`.

The old desktop/local-agent measurements are superseded diagnostics, not formal
calibration: they predate the reviewer-requested scorer and did not use this pinned
isolated environment. The metadata-less schema-invalid Gemini export is dropped.
