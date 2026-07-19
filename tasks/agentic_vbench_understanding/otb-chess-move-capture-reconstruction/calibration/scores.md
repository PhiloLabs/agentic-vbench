# Calibration Scores

This task is in post-review revision. The source has been replaced, and the new
104-ply move sequence and Black-win result have been human-verified. A fresh
full-media Codex diagnostic now passes the numerical hardness and long-horizon
gates; a natural-prompt Codex acceptance run and fresh Claude/Antigravity runs
remain pending. The required `single_frame` and `no_media` shortcut checks pass.

| run | status | reward | notes |
|---|---:|---:|---|
| oracle | passed | 1.0 | Human-verified move sequence and result; 287/287 checks passed across 104 plies and 26 captures. |
| empty baseline | passed | 0.0 | Empty `moves` and `capture_events` submission; 0/287 checks passed. |
| Codex CLI (`codex-replacement-chess-20260719T051110Z`) | passed diagnostic; natural-prompt rerun pending | 0.0250 | Fresh GPT-5.6 Sol full-media rollout on the replacement source; 9/360 checks, 60/104 plies, 18/26 captures, and 142 completed shell calls. The local prompt explicitly enforced the long-horizon minimum, so this run is archived but does not close the natural-prompt acceptance item. |
| Claude Code CLI | pending | n/a | Needs fresh rollout on replacement source. Old `claude-local-chess-20260710T223658Z` result was against the retired source and must not be used for acceptance. |
| Antigravity CLI | pending | n/a | Needs fresh rollout on replacement source. Old `antigravity-local-chess-fixed-default-20260711T034259Z` result was against the retired source and must not be used for acceptance. |
| Codex single-frame ablation (`codex-ablation-single-frame-20260719T012741Z`) | passed | 0.0058 | GPT-5.6 Sol (high reasoning) received one representative frame from 00:13:00. It produced a plausible but incorrect 50-ply history and 8 captures; only 2/343 checks passed. |
| Codex no-media ablation (`codex-ablation-no-media-20260719T012741Z`) | passed | 0.0 | GPT-5.6 Sol (high reasoning) received only the prompt and schema, returned `unknown` with empty move/capture lists, and passed 0/287 checks. |

## Post-Review Required Work

- The move sequence and Black-win result are verified. A second independent
  timestamp pass remains recommended for the +/- 6s annotations.
- Run a fresh Codex full-media rollout with only the benchmark instruction.
  Recalibrate with natural prompts only; do not count prompt-padded turn runs.
