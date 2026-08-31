# Calibration — badminton-momota-chou-2019-long-rally-checkpoints

| Harness | Harness version | Model | Reasoning | Reward | Tool-call turns | Trajectory |
|---|---|---|---|---:|---:|---|
| Codex CLI local pilot | 0.145.0 | GPT-5.6 Sol | xhigh | 0.081667 | 83 | local-only pilot |
| Codex through Harbor | 0.145.0 / Harbor 0.6.6 | GPT-5.6 Sol | xhigh | 0.088068 | 281 | `rollouts/codex-sol-xhigh.json` |
| Antigravity CLI | 1.1.8 | Gemini 3.5 Flash | high | 0.021095 | 132 | `rollouts/gemini-35-flash-high.jsonl` |
| Claude Code standalone Docker | 2.1.220 | Claude Opus 4.8 | high | 0.043344 | 1035 | `rollouts/claude-opus48-high.json` |

The revised reward is `qualification F1 * parent-metadata mean accuracy *
contact-timing F1 * checkpoint-state mean F1`. The checkpoint-state term is the
mean F1 of stroke index, hitter, hitter zone, receiver zone, and destination
zone; the parent term averages stroke-count and winner accuracy. Exact all-field
checkpoint F1 remains a diagnostic and is not a reward gate. All rewards here
were recalculated with this scorer.

| Run | Qualification F1 | Parent metadata | Contact timing F1 | Checkpoint-state mean F1 | Exact checkpoint F1 |
|---|---:|---:|---:|---:|---:|
| Codex through Harbor | 0.687500 | 0.750000 | 0.454545 | 0.375758 | 0.000000 |
| Gemini | 0.730769 | 0.315789 | 0.263158 | 0.347368 | 0.000000 |
| Claude | 0.476190 | 0.400000 | 0.533333 | 0.426667 | 0.033333 |

Formal Codex per-field diagnostics under the revised scorer:

| Diagnostic | Score |
|---|---:|
| stroke-count accuracy | 0.545455 |
| winner accuracy | 0.954545 |
| contact-timing F1 | 0.454545 |
| stroke-index F1 | 0.696970 |
| hitter F1 | 0.818182 |
| hitter-zone F1 | 0.151515 |
| receiver-zone F1 | 0.136364 |
| destination-zone F1 | 0.075758 |

Harbor runtime: 1h 25m 35s. The agent matched 22/26 reference rallies, and 11
matched rallies had both the correct stroke count and winner.

## Ground-truth provenance

The human-verified labels come from the pinned ShuttleSet source and its
six-annotator workflow. The complete-field audit is deterministic source
validation across all 26 rallies and 78 checkpoints, together with the
frame-rate and dataset-to-video alignment checks.

The pinned source CSVs reproduce the shipped task reference exactly:

| Scope | Field | Agreement | Discrepancies |
|---|---|---:|---:|
| qualifying set | rally membership | 26/26 | 0 |
| rally | set | 26/26 | 0 |
| rally | start time (`frame_num / 25`) | 26/26 | 0 |
| rally | stroke count | 26/26 | 0 |
| rally | winner | 26/26 | 0 |
| checkpoint | kind | 78/78 | 0 |
| checkpoint | stroke index | 78/78 | 0 |
| checkpoint | contact time (`frame_num / 25`) | 78/78 | 0 |
| checkpoint | hitter | 78/78 | 0 |
| checkpoint | hitter zone | 78/78 | 0 |
| checkpoint | receiver zone | 78/78 | 0 |
| checkpoint | destination zone | 78/78 | 0 |

No source-to-reference discrepancies were found, so no adjudications were
required.

## 25 fps contested sequences

The packaged video is constant 25 fps (40 ms per frame). Frame-by-frame review of
three of the shortest non-serve contact gaps in qualifying rallies found distinct
player actions for both strokes:

| Set | Rally start | Strokes | Contact times | Gap | Sequence |
|---:|---:|---:|---:|---:|---|
| 2 | 2236.48 s | 14-15 | 2248.96-2249.32 s | 9 frames / 0.36 s | smash to defensive return drive |
| 2 | 2807.08 s | 29-30 | 2835.68-2836.04 s | 9 frames / 0.36 s | rush to push |
| 3 | 5249.88 s | 23-24 | 5270.00-5270.32 s | 8 frames / 0.32 s | return net to rush |

The contact times are `frame_num / 25` from the pinned ShuttleSet source. The
surrounding frames in the packaged video preserve separate preparation and
follow-through cues rather than collapsing either pair into one event.

Gemini ran for 7m 30s in the task container. It returned 26 rallies, matched 19,
and had no exact checkpoints.

Claude ran as one checkpointed session across three segments (1h 25m 01s active
runtime). It returned 16 rallies and matched 10. Qualification F1 was 0.476190;
exact checkpoint F1 was 0.033333.

## Ablations

| Input | Harness | Model | Reward | Tool calls | Trajectory |
|---|---|---|---:|---:|---|
| video stream only; audio removed | Codex CLI 0.145.0 | GPT-5.6 Sol xhigh | 0.070958 | 208 | `rollouts/codex-sol-xhigh-video-only.jsonl` |
| audio stream only; video removed | Codex CLI 0.145.0 | GPT-5.6 Sol xhigh | 0.018403 | 60 | `rollouts/codex-sol-xhigh-audio-only.jsonl` |
| single frame at 3002.28 s + court grid | Codex CLI 0.145.0 | GPT-5.6 Sol xhigh | 0.000000 | 0 | `rollouts/codex-sol-xhigh-single-frame.jsonl` |
| no media | Antigravity CLI 1.1.8 | Gemini 3.5 Flash High | 0.000000 | 36 | `rollouts/gemini-35-flash-high-no-media.jsonl` |
| all 6176 one-second frames in 52 contact sheets, no tools | Codex CLI 0.145.0 | GPT-5.6 Sol xhigh | 0.013372 | 0 | `rollouts/codex-sol-xhigh-frame-dump-no-tools.jsonl` |

The video-only and audio-only MP4s were verified to contain exactly one H.264
video stream and one AAC audio stream, respectively. Both runs used the same
task instruction, Codex model and reasoning level, with network access disabled.
Video-only returned 17 rallies and matched 16; audio-only returned 22 and
matched 8.

The no-media run used an empty `/workspace/materials`, hid the image-baked media,
and had no search or browser tool calls. It returned an empty `rallies` list, with
qualification F1 0.0.

The single-frame run received only the frame at 3002.28 seconds and the supplied
court grid. It returned an empty `rallies` list.

The no-tools frame-dump run received every one-second frame in chronological order
as 52 row-major contact sheets. It returned 17 rallies, matched 8 reference rallies
for qualification F1 0.372093, and reconstructed no exact checkpoints. The
single-frame and frame-dump ablations used no tools.
