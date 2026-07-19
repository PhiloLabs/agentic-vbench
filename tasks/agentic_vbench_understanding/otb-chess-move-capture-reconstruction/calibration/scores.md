# Calibration Scores

This task is in post-review revision. The source has been replaced, and the new
104-ply move sequence and Black-win result have been human-verified. The
replacement source still needs fresh agent and ablation runs before submit-ready
review.

| run | status | reward | notes |
|---|---:|---:|---|
| oracle | passed | 1.0 | Human-verified move sequence and result; 287/287 checks passed across 104 plies and 26 captures. |
| empty baseline | passed | 0.0 | Empty `moves` and `capture_events` submission; 0/287 checks passed. |
| Codex CLI | pending | n/a | Needs fresh rollout on replacement source. Old `codex-local-chess-20260710T205129Z` result was against the retired source and must not be used for acceptance. |
| Claude Code CLI | pending | n/a | Needs fresh rollout on replacement source. Old `claude-local-chess-20260710T223658Z` result was against the retired source and must not be used for acceptance. |
| Antigravity CLI | pending | n/a | Needs fresh rollout on replacement source. Old `antigravity-local-chess-fixed-default-20260711T034259Z` result was against the retired source and must not be used for acceptance. |

## Post-Review Required Work

- The move sequence and Black-win result are verified. A second independent
  timestamp pass remains recommended for the +/- 6s annotations.
- Run `single_frame` and `no_media` ablations against the replacement source.
- Recalibrate with natural prompts only; do not count prompt-padded turn runs.
