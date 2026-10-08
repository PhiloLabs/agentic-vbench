# Calibration - robocup-2024-final-possession-chain-ledger

The final qualification pass must use the exact checked-in instruction, verifier,
task commit, and image built from the digest-pinned Dockerfile. The sole official
reward and difficulty gate is **exact order-preserving full-chain IoU (Jaccard)** (all five of
`half`, `team`, `kick_count`, `zone_path`, `terminal` must match). Precision and
recall are reported only as diagnostics. Do not mix results from earlier weighted or
partial-credit scorer revisions into this table.

The immutable v4 re-score archive records the judge SHA256
`4e7a7a9e565a39fa552a057f94ebf9c4945022f46f64f81d6fd728fef3ae6866`. That archive
is preserved as the historical re-score record. The checked-in judge currently has
SHA256 `328283c0ab99d4aa9e248c3ec60088adaf4b9b96bf50364a3c8dcdf0a4039efb`; all seven
retained answers were re-scored with that file as well. Their solution SHA256 values
and results are recorded in
[the current-judge re-score record](rescore-current-judge-20261008.json). All seven
results match the v4 archive; submitted solutions and trajectories were not modified.
The v4 re-score outputs, manifests, and copied submitted answers remain published in the immutable
[re-score bundle](https://github.com/shengjun-zhang/agentic-vbench/releases/download/robocup-possession-chain-iou-20260911-evidence-v4/rescored-retained-answers.tar.gz)
(`92e6bbe2927cd4dfcbe0c34834e398e316b051771885ac6815a6b3955734b1b2`).

The reviewer-audited first-half boundary chain now accepts its one explicit alternate
full path (`middle -> attacking` or `defensive -> attacking`). The tracked first kick
is `-1.994 m`, `0.006 m` from the `-2.0 m` boundary; every retained row re-scores to
the same value under this addition. It is not partial credit.

## End-to-end agents

Official reward is the `exact IoU` column. `precision`/`recall`/`n_pred`/`schema_valid`/
`exact` are diagnostics.

| harness | harness version | model | reasoning | exact IoU | precision | recall | n_pred | schema_valid | exact | tool-call turns | trajectory asset | whole-file SHA256 |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| Codex | Harbor 0.20.0 + direct Responses harness | GPT-5.6 Sol | high | 0.0000 | 0.0000 | 0.0000 | 8 | 8 | 0 | 64 | [release bundle](https://github.com/shengjun-zhang/agentic-vbench/releases/download/robocup-possession-chain-iou-20260909-evidence-v2/codex-e2e.tar.gz) | `73d01016602e6f57f2c8eda118530ec27498cc8a8a584fa586520b3356dbbce7` |
| Claude Code | Harbor 0.20.0 + manual wrapper | Claude Opus 4.8 | xhigh | 0.0571 | 0.1000 | 0.1176 | 20 | 20 | 2 | 416 | [release bundle](https://github.com/shengjun-zhang/agentic-vbench/releases/download/robocup-possession-chain-iou-20260909-evidence-v2/claude-e2e.tar.gz) | `b38a63503c592c43c7684c2e613ce0d404089c6d73e0241d1373a455e05df97c` |
| Antigravity CLI | 1.1.21 | Gemini 3.5 Flash | high | 0.0213 | 0.0253 | 0.1176 | 79 | 79 | 2 | 145 | [release bundle](https://github.com/shengjun-zhang/agentic-vbench/releases/download/robocup-possession-chain-iou-20260911-evidence-v4/antigravity-e2e.tar.gz) | `5368b2aff2514da8a06d4c7f1dedc6487bb0fa64f90c95637414342e7aa1ad3d` |

The selected Claude Code row is the clean September 6 run. Its exact IoU is `0.0571`,
below the `0.10` gate, with 20 submitted chains and 2 exact matches.

## Anti-shortcut ablations

All rows are single-attempt GPT-5.6 Sol runs under the finalized scorer. The first
three runs append the documented forced-answer suffix after the original instruction;
its SHA256 is `5c31753b603af21b483f749a6379996b98d665e12ac7207dcf011d83c596ab6a`.
Exact input conditions are fixed in `ablations/README.md`.

| condition | exact IoU | precision | recall | n_pred | schema_valid | exact | tool-call turns | trajectory asset | whole-file SHA256 |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| Prompt/schema, no media | 0.0000 | 0.0000 | 0.0000 | 1 | 1 | 0 | 7 | [release bundle](https://github.com/shengjun-zhang/agentic-vbench/releases/download/robocup-possession-chain-iou-20260909-evidence-v2/ablation-nomedia-forced.tar.gz) | `7750ae2d6b578020ab5877d141a15a3e1bf23b9774ebfa2393450eda6874b524` |
| One temporal-midpoint frame | 0.0000 | 0.0000 | 0.0000 | 1 | 1 | 0 | 7 | [release bundle](https://github.com/shengjun-zhang/agentic-vbench/releases/download/robocup-possession-chain-iou-20260909-evidence-v2/ablation-single-frame-forced.tar.gz) | `5506fc4fa50bdca06ad2d4fe8b9451c0b66e844d249f710ad81ee63d1a50d66f` |
| OCR-only timeline | 0.0000 | 0.0000 | 0.0000 | 1 | 1 | 0 | 8 | [release bundle](https://github.com/shengjun-zhang/agentic-vbench/releases/download/robocup-possession-chain-iou-20260909-evidence-v2/ablation-ocr-forced.tar.gz) | `f3aae9b201a5db27e70170ef4e9ba4a4e5d1d65cb6e641573c6d09f1d16a2389` |
| Every native frame pasted, no tools (independent replicate) | 0.0185 | 0.0263 | 0.0588 | 38 | 38 | 1 | 0 | [release bundle](https://github.com/shengjun-zhang/agentic-vbench/releases/download/robocup-possession-chain-iou-20260909-evidence-v2/ablation-allframes-notools.tar.gz) | `32e0c7e0445c661572d8d9e4b3e0f2380a06cf052213c93abb4bda2e3a5a0002` |

The three forced-answer rows each submitted one non-empty schema-valid ledger and
scored exact IoU `0.0000`. The all-frame row is the pre-registered independent
replicate: one exact full-chain match out of 38 submitted
entries against 17 ground-truth chains gives precision `0.0263`, recall `0.0588`, and
exact IoU `0.0185`. It used all 44,032 decoded frames in 111 chronological 20-by-20
sheets, one model turn, and no tools or subagents. The earlier all-frame run remains a
reproducibility diagnostic rather than the selected row.

The immutable bundle archives are published in the
[RoboCup evidence releases](https://github.com/shengjun-zhang/agentic-vbench/releases/tag/robocup-possession-chain-iou-20260911-evidence-v4);
their whole-file SHA256 values are:

| bundle | SHA256 |
|---|---|
| `codex-e2e.tar.gz` | `73d01016602e6f57f2c8eda118530ec27498cc8a8a584fa586520b3356dbbce7` |
| `claude-e2e.tar.gz` | `b38a63503c592c43c7684c2e613ce0d404089c6d73e0241d1373a455e05df97c` |
| `antigravity-e2e.tar.gz` | `5368b2aff2514da8a06d4c7f1dedc6487bb0fa64f90c95637414342e7aa1ad3d` |
| `rescored-retained-answers.tar.gz` | `92e6bbe2927cd4dfcbe0c34834e398e316b051771885ac6815a6b3955734b1b2` |
| `ablation-nomedia.tar.gz` | `ac7228cd359937cb1ea81c30983f1927f3ed96cb066141a03517282ab257fd68` |
| `ablation-single-frame.tar.gz` | `8e21a31a1fcff64dfce741fa316d7602b63cfdd9b785c4d5b4a1909c645308ac` |
| `ablation-ocr.tar.gz` | `285f1cc224822a719b4bce3365a6b33a75642393d8a809d7ad32598718e0e42d` |
| `ablation-allframes-notools.tar.gz` | `32e0c7e0445c661572d8d9e4b3e0f2380a06cf052213c93abb4bda2e3a5a0002` |
| `ablation-nomedia-forced.tar.gz` | `7750ae2d6b578020ab5877d141a15a3e1bf23b9774ebfa2393450eda6874b524` |
| `ablation-single-frame-forced.tar.gz` | `5506fc4fa50bdca06ad2d4fe8b9451c0b66e844d249f710ad81ee63d1a50d66f` |
| `ablation-ocr-forced.tar.gz` | `f3aae9b201a5db27e70170ef4e9ba4a4e5d1d65cb6e641573c6d09f1d16a2389` |
| `allframes-inputs-and-request.tar.gz` | `cfb8083be72ce883a93d3f8e8c05750eafcab869355655321db8fd9dc5e1c277` |

Condition-specific provenance:

| condition | runtime image ID | degraded-input identity |
|---|---|---|
| No media | `sha256:24cd22f53369b31ab4b10ad6cad3e95573c96882466ae242c8bcf92a53703b5f` | both MP4 locations absent |
| Single frame | `sha256:3fe7e6d2c2933cb460f5351ae0c8eb497124e01b1cc3ce884c3c3b24541b86a3` | F22016, one 1280x720 frame; media SHA256 `75433540904e9a9d966d7dfdaf8d8e60134c2d20da5e0fd9d2ed6245a8f61ace` |
| OCR only | `sha256:f27267214f7093b3e1466d48f3aba88b2c1dba3e5a4ec860110d40969e5958fe` | 177 timestamps and 6,175 text boxes; artifact SHA256 `9a59563e7d7df2127f7b0346d269069cd0276feaa4b55d6d17a4419a4f5703c8` |
| All frames, no tools replicate | `sha256:73a4d049db3ada73882107a4e792c5e3340195224a205c7453de8bb3a4410912` | 44,032 frames; 111-sheet manifest SHA256 `011a16c3aafee19272d9eeab8321abd4110ae7b8eafd41f86c40dfec6f033325` |

`allframes-inputs-and-request.tar.gz` retains the 111 original JPEG sheets, their
per-sheet manifest, prompt, Responses record, trajectory, submitted solution,
verifier output, preregistration, and no-tools runner. These materials make the
input sequence and request context reconstructible without asserting retention of
one complete serialized API request.

## Run identity

Record these once the final image is built and do not change the task between rows:

| item | value |
|---|---|
| task commit | `990711fbe7be8854dfa07007f7a60810b1f9f064` |
| Harbor version | `0.20.0` |
| original qualification judge SHA256 | `1ff25ed4e3a3721906950f035704ee2e6a5c8553b4f601e76291e3a39b6cdbcd` |
| current checked-in judge SHA256 | `328283c0ab99d4aa9e248c3ec60088adaf4b9b96bf50364a3c8dcdf0a4039efb` |
| Codex image ID | `sha256:ae98225846c1c83bb058392f1582e14b1dffea753d3a0ed2d38832a831631a39` |
| Claude image ID | `sha256:ed8de26cfd100adf229adad2e0b8d70984d4ba002ef218b6145f57885e5937dc` |
| Antigravity image ID | `sha256:b0d91055dca04597508994f693c9cc00b16bfeb5bfa2130a349fde0e66a7eeee` |
| base image digest | `python:3.12-slim@sha256:2c941e860699f878900b0edc2403613c234d4b32eda3cc9fa7036991a2a63c4a` |
| default materials URL | `https://github.com/shengjun-zhang/agentic-vbench/releases/download/robocup-possession-chain-media-20260911/match.mp4` |
| media SHA256 | `076bcc59fc48443d24a72a87162021470b9e645b41c858c3ffa5b5b25bae36cd` |

## Counting rules

The official reward is exact full-chain IoU. For Harbor ATIF trajectories, count
tool-call turns as agent-authored steps containing at least one `tool_calls` object
across the main trajectory and any explicitly referenced subagent trajectories.
Record the raw tool-call count and any harness-native comparison count separately when
they differ. A run clears the difficulty gate only when exact full-chain IoU is below
`0.10` for every reported strong-agent and ablation row, and a genuine end-to-end
attempt exceeds 50 tool-call turns.

Antigravity's 145 tool-call turns are the non-empty action records before the final
answer in its retained CLI narration. The release also includes a path-sanitized
outer App orchestration record, `outer-app-transcript_full.jsonl`, SHA256
`4612e5c2c6c062fef3bf9ed420b17c4bbfe15d22ff489d3beffa1030fb11bc61`
(509 records; 219 outer-App tool-call records). The latter is not counted as an
inner task-agent tool trace; its scope is recorded in the bundle manifest.

The old desktop/local-agent measurements are superseded diagnostics, not formal
calibration: they predate the reviewer-requested scorer and did not use this pinned
isolated environment. The metadata-less schema-invalid Gemini export is dropped.

## Media acquisition validation

The ordinary no-argument Docker build was rerun after the calibration assets were
published. It fetched the public release asset at the default URL recorded above,
then verified SHA256 `076bcc59fc48443d24a72a87162021470b9e645b41c858c3ffa5b5b25bae36cd`
and ffprobe values `1280x720`, `50/1`, and `880.640000` before completing. The
resulting image manifest was
`sha256:368d5d11838495230680432ac03ccec00df418e5e0462c6803d2b148455d3d44`.
This is infrastructure validation only; the retained trajectories above remain
byte-identical and were not rerun.
