# Calibration — badminton-momota-chou-2019-long-rally-checkpoints

| Harness | Harness version | Model | Reasoning | Reward | Tool-call turns | Trajectory |
|---|---|---|---|---:|---:|---|
| Codex CLI local pilot | 0.145.0 | GPT-5.6 Sol | xhigh | 0.000000 | 83 | local-only pilot |
| Codex through Harbor | 0.145.0 / Harbor 0.6.6 | GPT-5.6 Sol | xhigh | 0.000000 | 281 | `rollouts/codex-sol-xhigh.json` |
| Antigravity CLI | 1.1.8 | Gemini 3.5 Flash | high | 0.000000 | 132 | `rollouts/gemini-35-flash-high.jsonl` |
| Claude Code standalone Docker | 2.1.220 | Claude Opus 4.8 | high | 0.015873 | 1035 | `rollouts/claude-opus48-high.json` |

Harbor runtime: 1h 25m 35s. The agent matched 22/26 reference rallies;
qualification F1 was 0.687500. Eleven matched rallies had exact stroke count and
winner. Conditional checkpoint F1 was 0.0.

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
and had no exact checkpoints. Qualification F1 was 0.730769; conditional checkpoint
F1 was 0.0.

Claude ran as one checkpointed session across three segments (1h 25m 01s active
runtime). It returned 16 rallies and matched 10. Qualification F1 was 0.476190;
conditional checkpoint F1 was 0.033333.

## Ablations

| Input | Harness | Model | Reward | Tool calls | Trajectory |
|---|---|---|---:|---:|---|
| single frame at 3002.28 s + court grid | Codex CLI 0.145.0 | GPT-5.6 Sol xhigh | 0.000000 | 0 | `rollouts/codex-sol-xhigh-single-frame.jsonl` |
| no media | Antigravity CLI 1.1.8 | Gemini 3.5 Flash High | 0.000000 | 36 | `rollouts/gemini-35-flash-high-no-media.jsonl` |
| all 6176 one-second frames in 52 contact sheets, no tools | Codex CLI 0.145.0 | GPT-5.6 Sol xhigh | 0.000000 | 0 | `rollouts/codex-sol-xhigh-frame-dump-no-tools.jsonl` |

The no-media run used an empty `/workspace/materials`, hid the image-baked media,
and had no search or browser tool calls. It returned an empty `rallies` list, with
qualification F1 0.0.

The single-frame run received only the frame at 3002.28 seconds and the supplied
court grid. It returned an empty `rallies` list.

The no-tools frame-dump run received every one-second frame in chronological order
as 52 row-major contact sheets. It returned 17 rallies, matched 8 reference rallies
for qualification F1 0.372093, and reconstructed no exact checkpoints. Both Codex
ablations used no tools and scored 0.0.
