# Calibration — pac12-2018-balance-beam-routine-timeline

The scored contract uses strict one-to-one F1 over `start_time`, `end_time`,
`dismount_takeoff_time`, exact `school`, exact `gymnast_name`, exact
three-decimal `beam_score`, and a tightly localized `score_time`.

## Status

The seven-field annotation gate, all three final-contract strong-agent runs,
and all five shortcut ablations are complete. Each run used a fresh workspace,
one non-resumable 5,400-second outer deadline, the same locked source bytes,
and the same frozen scored contract. No run timed out, resumed, restarted, or
used task-side web/network access.

| harness | harness version | model | reasoning | reward | completed tool calls | elapsed seconds | published trajectory |
|---|---|---|---|---:|---:|---:|---|
| Antigravity CLI | 1.1.22 | `gemini-3.5-flash-high` | high | **0.0** | **360** | 1,286.372 | `rollouts/antigravity-seven-field-20260827T200119Z/antigravity-gemini-3.5-flash-high.public.jsonl` |
| Codex CLI | 0.146.0-alpha.3.1 | `gpt-5.6-sol` | xhigh | **0.086957** | **55** | 2,128.389 | `rollouts/codex-seven-field-20260827T184157Z/codex-gpt-5.6-sol-xhigh.public.jsonl` |
| Claude Code CLI | 2.1.220 | `claude-opus-4-8` | high | **0.0** | **56** | 1,251.308 | `rollouts/claude-seven-field-20260827T205411Z/claude-code-opus-4.8-high.public.jsonl` |

All three rewards are below 0.10 and all three completed-tool-call counts exceed
50. Codex predicted 23 records and matched 2 complete records. Claude predicted
2 records and Antigravity predicted 3; neither had a strict complete-record
match. Each packaged run retains the rendered prompt, source/input manifest,
raw solution, checkpoint, run metadata, verifier result, real tool-call count,
network/secret audit, versions, and SHA-256 evidence. Publication of native
visual payload binaries is subject to the requested reviewer rights exception.

Required calibration gates:

- oracle reward: at least 0.999;
- empty baseline: at most 0.10;
- Antigravity, Codex, and Claude rewards: each below 0.10;
- each strong-agent rollout: more than 50 real tool-call turns;
- each run: one fresh workspace and one non-extendable 5,400-second process;
- each shortcut ablation: at most 0.15.

## Shortcut ablations

The five Codex controls were launched as one fresh batch against the final
seven-field scorer. Each delivered only the stated degraded input. Raw local
artifacts remain available for audit; the paths below are the compact,
identity-safe published trajectories bound to their originals by SHA-256.

| control | delivered input | model / reasoning | reward | completed tool calls | elapsed seconds | published trajectory |
|---|---|---|---:|---:|---:|---|
| no media | prompt and schema only; no media file | `gpt-5.6-sol` / xhigh | **0.0** | 6 | 40.999 | `ablations/codex-no-media-20260827T214117Z/codex-gpt-5.6-sol-xhigh.public.jsonl` |
| single frame | one full-size frame at source midpoint 4,178.167 s | `gpt-5.6-sol` / xhigh | **0.0** | 5 | 41.690 | `ablations/codex-single-frame-20260827T214117Z/codex-gpt-5.6-sol-xhigh.public.jsonl` |
| frame dump, no tools | 8,356 one-frame-per-second samples packed into 14 image attachments; zero tool use allowed | `gpt-5.6-sol` / medium | **0.0** | 0 | 294.279 | `ablations/codex-frame-dump-no-tools-20260827T214117Z/codex-gpt-5.6-sol-medium.public.jsonl` |
| video only | full locked video with every audio stream removed | `gpt-5.6-sol` / xhigh | **0.130435** | 138 | 1,908.435 | `ablations/codex-video-only-20260827T214117Z/codex-gpt-5.6-sol-xhigh.public.jsonl` |
| audio only | full 8,356.334-second Opus stream with no video stream | `gpt-5.6-sol` / xhigh | **0.0** | 361 | 4,155.995 | `ablations/codex-audio-only-20260827T214117Z/codex-gpt-5.6-sol-xhigh.public.jsonl` |

All five rewards satisfy the required maximum of 0.15. The video-only result
matched 3 of 23 strict records; every other control matched zero complete
records. The frame-dump trajectory contains exactly zero completed tool calls,
as required by that control.

## Verified preflight

- oracle: 1.0;
- empty list: 0.0;
- malformed JSON: 0.0;
- invalid schema: 0.0 for the whole submission;
- reversed oracle: 0.0 for the whole submission;
- verifier unit tests: 21 passing;
- source SHA-256:
  `7dfc9e139254cc9480948af734988bdebc796c89c6e5d439055a248c251130cb`;
- source probe: 139.3 minutes, 1280×720.

## Superseded runs

Earlier calibration is historical only. It cannot support this revision because
the schema and reward now also require a tightly localized score time. Older
runs also used
continuations or incomplete packaged visual artifacts, so their tracked
trajectory copies were removed rather than presented as fresh evidence.

| harness | old score | reason ineligible |
|---|---:|---|
| Antigravity / Gemini 3.5 Flash High | 0.0 | old four-field task; continued run |
| Codex / GPT-5.6 Sol xhigh | 0.0 | old four-field task |
| Claude Code / Opus 4.8 high | 0.042553 | old four-field task; continued run; visual payloads redacted |

## Fresh-run protocol

`runpack/README.md` stages empty workspaces, saves each exact initial prompt,
enforces one total 90-minute process deadline, and records raw unredacted native
outputs plus SHA-256 manifests. It documents the clean local/offline path used
for these runs. As of 2026-08-27, the maintainer has not yet answered the
requested host-run exception; the Dockerfile remains the reproducible
environment description.
