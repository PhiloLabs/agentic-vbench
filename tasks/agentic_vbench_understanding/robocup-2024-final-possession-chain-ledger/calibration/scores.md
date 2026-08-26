# Calibration - robocup-2024-final-possession-chain-ledger

The final qualification pass must use the exact checked-in instruction, verifier,
task commit, and image built from the digest-pinned Dockerfile. The required
calibration statistic is exact order-preserving full-chain precision. The retained
partial-credit F1 is reported separately as a scorer diagnostic; it is not the
calibration gate. Do not mix results from earlier scorer or prompt revisions into
this table.

## End-to-end agents

| harness | harness version | model | reasoning | exact precision (gate) | partial-credit F1 (diagnostic) | tool-call turns | trajectory asset | whole-file SHA256 |
|---|---|---|---|---:|---:|---:|---|---|
| Codex | Harbor 0.20.0 + direct Responses harness | GPT-5.6 Sol | high | 0.0000 | 0.1600 | 64 | retained raw trajectory | `a426ec0c084362eb5fe6de75643d18ac151d9d1252e08e81976c97cc278d97d3` |
| Claude Code | Harbor 0.20.0 + manual wrapper | Claude Opus 4.8 | xhigh | 0.0952 | 0.2368 | 173 | retained raw trajectory | `faacb6ba2ecadf161063ab6ee4f15c2993a79f94fbeb0a8ebdda4735a5539fda` |
| Antigravity CLI | 1.1.21 | Gemini 3.5 Flash | high | 0.0253 | 0.1224 | 145 | retained native log | `ad1f9812032649f8a59c8a996da901e88ca9814f32e7885d44429c29f1b96350` |

## Anti-shortcut ablations

All four rows are real GPT-5.6 Sol runs under the final image and scorer. Exact input
conditions are fixed in `ablations/README.md`.

| condition | exact precision (gate) | partial-credit F1 (diagnostic) | tool-call turns | trajectory asset | whole-file SHA256 |
|---|---:|---:|---:|---|---|
| Prompt/schema, no media | 0.0000 | 0.0000 | 2 | pending fork release upload | `55dbfa7c3be082e6c3b7c523c3d93987e53cc59952204b4f33043f6323dceab1` |
| One temporal-midpoint frame | 0.0000 | 0.0000 | 7 | pending fork release upload | `b3eb7a96e0a5df534223c06cdeda6f66e3f5140e2615fd7fe37fd8dc70383250` |
| OCR-only timeline | 0.0000 | 0.0000 | 4 | pending fork release upload | `6ca09d160ef1c730367f24fc269682d5ea4f83587138099a0c1d829bd9a8c2c3` |
| Every native frame pasted, no tools (independent replicate) | 0.0263 | 0.2091 | 0 | pending fork release upload | `06a8d15016e4f0688121875450c2ff363911fd42af2a129d9560d509012b25ba` |

The reported all-frame row is the pre-registered independent replicate, with exact
precision 0.0263. It used all 44,032 decoded frames in 111 chronological 20-by-20
sheets, one model turn, and no tools or subagents. The earlier run remains a
reproducibility diagnostic rather than the selected row, with exact precision 0.0976.

Condition-specific provenance:

| condition | runtime image ID | degraded-input identity |
|---|---|---|
| No media | `sha256:24cd22f53369b31ab4b10ad6cad3e95573c96882466ae242c8bcf92a53703b5f` | both MP4 locations absent |
| Single frame | `sha256:3fe7e6d2c2933cb460f5351ae0c8eb497124e01b1cc3ce884c3c3b24541b86a3` | F22016, one 1280x720 frame; media SHA256 `75433540904e9a9d966d7dfdaf8d8e60134c2d20da5e0fd9d2ed6245a8f61ace` |
| OCR only | `sha256:f27267214f7093b3e1466d48f3aba88b2c1dba3e5a4ec860110d40969e5958fe` | 177 timestamps and 6,175 text boxes; artifact SHA256 `9a59563e7d7df2127f7b0346d269069cd0276feaa4b55d6d17a4419a4f5703c8` |
| All frames, no tools replicate | `sha256:73a4d049db3ada73882107a4e792c5e3340195224a205c7453de8bb3a4410912` | 44,032 frames; 111-sheet manifest SHA256 `011a16c3aafee19272d9eeab8321abd4110ae7b8eafd41f86c40dfec6f033325` |

## Run identity

Record these once the final image is built and do not change the task between rows:

| item | value |
|---|---|
| task commit | `7553740b95925b21a11000ec4d7256c127020577` |
| Harbor version | `0.20.0` |
| image repository digest or local image ID | pending |
| base image digest | `python:3.12-slim@sha256:2c941e860699f878900b0edc2403613c234d4b32eda3cc9fa7036991a2a63c4a` |
| media SHA256 | `076bcc59fc48443d24a72a87162021470b9e645b41c858c3ffa5b5b25bae36cd` |

## Counting rules

For Harbor ATIF trajectories, count tool-call turns as agent-authored steps containing
at least one `tool_calls` object across the main trajectory and any explicitly
referenced subagent trajectories. Record the raw tool-call count and any harness-native
comparison count separately when they differ. A run clears the difficulty gate only
when exact precision is below `0.10` for every reported strong-agent and ablation row,
and a genuine end-to-end attempt exceeds 50 tool-call turns.

Antigravity records its tool progress in its native agent log rather than ATIF
`tool_calls` objects. Its 145 tool-call turns are the non-empty action records before
the final answer in that retained log.

The old desktop/local-agent measurements are superseded diagnostics, not formal
calibration: they predate the reviewer-requested scorer and did not use this pinned
isolated environment. The metadata-less schema-invalid Gemini export is dropped.
