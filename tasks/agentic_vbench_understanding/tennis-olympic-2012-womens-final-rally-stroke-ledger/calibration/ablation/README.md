# Ablation trajectories

One raw transcript per anti-shortcut ablation, kept so a reviewer can audit the run
rather than trust a summary. Results, harness details, and analysis live in
`../scores.md`.

| ablation | score | files |
|---|---:|---|
| `no_media` | 0.000000 | `ablation-no_media.*` |
| `single_frame` | 0.000000 | `ablation-single_frame.*` |
| `video_only` | 0.090909 | `ablation-video_only.*` |
| `audio_only` | **0.018570** — 866-stroke best-effort attempt | `ablation-audio_only.*` |
| `frame_dump_no_tools` | 0.000000 | `ablation-frame_dump_no_tools.*` |

Each completed run keeps `.jsonl` (trajectory), `.reward.json` / `.reward.txt` (the
shipped `judge.py` verdict), and `.solution.json` when one was produced. The current
`audio_only` `.jsonl` is the native Codex rollout; it also keeps Harbor's normalized
`.trajectory.json` and its non-empty solution. This run used `gpt-5.6-sol` at medium
reasoning through Codex CLI 0.154.0 and Harbor 0.22.0. Its runtime exposed only
`match.m4a` and `vocabulary.json`; its 47 tool calls contained no web lookup, external
URL, `curl`, or `wget`.
