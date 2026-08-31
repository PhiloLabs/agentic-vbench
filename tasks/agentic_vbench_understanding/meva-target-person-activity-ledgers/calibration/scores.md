# Calibration

The frozen verifier scores 29 activity assignments for ten video-local roster
targets.

## Submission status

All three required rows clear the measured difficulty gate.

## Anchors

| harness | version | run | score |
|---|---|---|---:|
| Harbor | 0.6.6 | exact oracle | 1.000000 |
| Harbor | 0.6.6 | empty submission | 0.000000 |

## Required agent calibration

| harness | harness version | model | reasoning | score | tool-call turns | trajectory |
|---|---|---|---|---:|---:|---|
| Codex CLI | 0.147.0 | GPT-5.6 Sol | high | 0.009443 | 80 | `rollouts/codex-gpt-5.6-sol.jsonl` |
| VS Code Claude Agent SDK | 0.60.0 | Claude Opus 4.8 | high | 0.004100 | 115 parent; 554 including nested agents | `rollouts/claude-opus-4.8.jsonl` |
| Antigravity CLI | 1.1.12 | Gemini 3.6 Flash High | high | 0.003459 | 220 | `rollouts/antigravity-gemini-3.6-flash-high.jsonl` |

## Required degraded-input runs

| ablation | harness | harness version | model | score | tool-call turns | trajectory |
|---|---|---|---|---:|---:|---|
| no media | GitHub Copilot CLI | 1.0.79-9 | GPT-5.6 Sol | 0.000000 | 11 | `rollouts/ablation-no-media.jsonl` |
| single frame | GitHub Copilot CLI | 1.0.79-9 | GPT-5.6 Sol | 0.000000 | 24 | `rollouts/ablation-single-frame.jsonl` |
| one-frame-per-second dump, no inspection tools | GitHub Copilot CLI | 1.0.79-9 | GPT-5.6 Sol | 0.001106 | 4 | `rollouts/ablation-frame-dump-no-tools.jsonl` |

Tool-call turns are counted from each harness's own tool-invocation record, so
the rule differs by harness: Copilot CLI `tool.execution_start`; Codex CLI
distinct `item.started`; Claude Agent SDK `chat/toolCallStart`; Antigravity CLI
distinct `step_update.step_index` where `step_type` is `tool`. Applying the
matching rule to the file each row links to reproduces the number in that row.
For the Claude row the split is by `channel`: the `ahp-chat://default/…` channel
gives the 115 parent turns, and all channels together give 554.

Each of the three ablation files above is a complete raw stream that ends in a
`result` event with `exitCode` 0.

Harness-level withholding for the frame-dump row is checkable in that stream's
`session.info` line: it disables `bash`, `glob`, `rg`, and `view` on top of the
set disabled in the other two runs. The inspection tools were removed by harness
configuration, not merely discouraged by the prompt.

The no-media run ended without writing a submission at all — its own summary
records `Blocked: /workspace/materials is empty`. Its 0.000000 therefore comes
from the missing-submission path and is equivalent to the empty-submission
anchor above, rather than being an independent probe of schema guessability.

## Deterministic identity shortcuts

| submission | score |
|---|---:|
| all gold-timed events assigned to one target | 0.003344 |
| all gold-timed events copied to every target | 0.032963 |
| correct target activity types at wrong times | 0.000116 |
| all events shifted by five seconds | 0.000470 |

The PR tree keeps one complete trajectory per required harness plus the measured
degraded-input trajectories.
