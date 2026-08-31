# Codex Experiment Status

This is a status snapshot for the Melee causal-ledger calibration. The formal
metric throughout is exact event-level F1; see `calibration/scores.md` for the
submission table.

## Fixed Conditions

- Model: `gpt-5.6-sol`
- Provider route: `https://tokken.cc/v1`
- Codex agent version in Harbor trials: `0.147.0-alpha.6.5`
- Reasoning: `high` where recorded
- Source video SHA256: `02f18fd7f4796800eece0400b1b1f315a36778b57b9ef4a64d1b30aa3b539749`
- Formal prompt SHA256: `911e5db8cefdff943ba7e411e1e3ee74253abf132e3e4fa78af57c4c0c863caf`

## Codex Runs

| condition | latest trial | status | exact F1 | interpretation |
|---|---|---:|---:|---|
| Full baseline r3 | `jobs/melee-codex-full-baseline-local-media-r3/melee-normal__VmESmXy` | completed | `0.0132` | Codex clean calibration; 47 predictions, 1 exact match |
| OCR-only | `melee-harbor-calibration/jobs/melee-codex-ocr-only-ablation-20260825-r2/melee-ocr__sTNzggH` | completed | `0.0000` | completed ablation |
| Single-frame | `melee-harbor-calibration/jobs/melee-codex-single-frame-ablation-20260825-r3/melee-singleframe__fSsipBY` | completed | `0.0000` | completed ablation |
| No-media | `jobs/melee-no-media-20260825-r3/no-media__RxyYdkD` | completed | `0.0000` | completed ablation |
| All-frames/no-tools | `jobs/melee-allframes-notools-20260825-r7/all-frames-no-tools__9c3LM75` | completed | `0.0000` | completed ablation under the no-tools/contact-sheet condition |

Earlier all-frames attempts r6 and r8 are not additional valid final results:
r6 completed with exact F1 `0.0000`, while r8 was cancelled after a transport stall.
The older pending directories r2-r5 are stale launch artifacts and should not be
counted as running experiments.

## Claude and Antigravity Submission

The existing Claude and Antigravity entries are retained as the submitted full
baseline results:

- Claude local agent: `claude-sonnet-5`, version `2.1.209`, exact F1 `0.0000`.
- Antigravity: `Gemini 3.5 Flash`, `Antigravity.app 2.3.1`, exact F1 `0.0169`.

No additional Claude or Antigravity run is required for this submission.

The prepared instructions are:

- `calibration/manual-reruns-20260825/claude-code/APP_HANDOFF.md`
- `calibration/manual-reruns-20260825/antigravity/APP_HANDOFF.md`

These entries are the final cross-harness baseline values used for submission.

## Recommended Next Actions

1. Treat Codex full baseline r3, OCR-only r2, single-frame r3, no-media r3, and
   all-frames/no-tools r7 as the completed Codex evidence.
2. Keep the Claude and Antigravity clean-calibration entries together with their
   retained rollout artifacts; no additional run is required.
