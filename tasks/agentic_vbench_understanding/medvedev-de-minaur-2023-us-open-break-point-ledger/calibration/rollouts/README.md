# Calibration rollout artifacts

This directory contains the current-schema, full-media Codex calibration. Ablation
trajectories are separated under `../ablations/`, matching the layout used by PR
#84. Cross-harness attempts that never produced a valid terminal trajectory are
compact `NO_SCORE` records under `../failures/` and are not mixed with scored runs.

## Full-media run

| field | value |
|---|---|
| harness | Codex CLI 0.149.1 |
| model | GPT-5.6 Sol |
| reasoning | high |
| trial | `full-media__w5fcyND` |
| input | canonical silent 1280x720 match |
| predicted events | 17 |
| ordered identity matches | 16/16 |
| ATIF tool-call turns | 247 |
| native operations | 233 |
| runtime | 3691.0 s |
| official hierarchical reward | **0.3305** |
| exact-event diagnostic | 0.0 |

The agent recovered 79/144 summary atoms and 136 ordered shot-field atoms. The
event-wise bottleneck gives hierarchical true-positive credit `5.4539`, precision
`0.3208`, recall `0.3409`, and F1 `0.3305`. No event was fully exact.

## Files

- `*.raw.txt` is the complete native Codex output stream.
- `*.input-manifest.txt` records the agent-visible input and frozen task identity.
- `*.submitted-solution.json` is the exact terminal submission.
- `*.reward.json` is the unaltered generation-time exact-judge reward.
- `*.validation.json` binds the raw run, image, overlay, old judge, submission,
  gateway envelope, and tool-call counts under `avb-formal-run-strict-v3`.
- `*.hierarchical-verifier-details.json` is the deterministic regrade with the
  current official verifier.

The distinction between the last three files is intentional. The raw trajectory
was generated before the reviewer-requested scoring revision. Its strict-v3 record
remains valid provenance for what the model saw and did, but it does not validate
the later metric. The current verifier details are regenerated from the frozen
submitted solution and checked by `../test_regrades.py`.

```text
fixed image: avb-medvedev-codex@sha256:390fb56051fafb49b5b4b797cb15704469294f816255994e9ee0fd21fe2da06b
canonical silent media sha256: d61bee17596a28dbc8f8b607e4fc0dd6542885dbe9cdad18e1953e89363b0860
instruction sha256: 2b025b557a17f2443e9b8f5951ee19562eee570038d092a7757b957555d1cd55
oracle script sha256: 75c03d3084ebc3670ffbf77ee2ca5b0a46f16f8a4feb6b1d834c80aaa3a4c5c5
```

The generation-time `.validation.json` records the original exact-judge and test
hashes. Current source hashes are listed in `../../SPEC.md` and the directory
`SHA256SUMS` file.

## Scope

This is a WIP calibration candidate. A score of `0.3305` is above the preferred
`<0.10` difficulty threshold. Claude Code Fable/Opus and native Antigravity
Flash/Pro remain unscored because no valid terminal trajectory is available. The
PR must not claim that calibration conditions are fully satisfied.
