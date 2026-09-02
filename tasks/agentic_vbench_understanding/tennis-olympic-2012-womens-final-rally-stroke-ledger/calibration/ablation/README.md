# Ablation trajectories

One raw transcript per anti-shortcut ablation, kept so a reviewer can audit the run
rather than trust a summary. Results and analysis live in `../scores.md`; the staging
and grading scripts live in `../runpack/`.

| ablation | score | files |
|---|---:|---|
| `no_media` | 0.000000 | `ablation-no_media.*` |
| `single_frame` | 0.000000 | `ablation-single_frame.*` |
| `video_only` | 0.090909 | `ablation-video_only.*` |
| `audio_only` | **0.150685** — fails the `<= 0.15` bar | `ablation-audio_only.*` |
| `frame_dump_no_tools` | 0.000000 | `ablation-frame_dump_no_tools.*` |

Each run keeps `.jsonl` (trajectory), `.solution.json` (what was graded),
`.reward.json` / `.reward.txt` (the shipped `judge.py` verdict), and `.err` where the
CLI wrote one. Every trajectory was audited for web lookups and for recall of the
match; none was found.

`ablation-audio_only.killed-run.*` is a first `audio_only` attempt stopped externally
after one tool call. It produced no solution and is retained only so the gap in the
timestamps is accounted for — it is not a measurement.
