# Calibration Scores

This task is in post-review revision. The source has been replaced, and the new
104-ply move sequence and Black-win result have been human-verified. A fresh
natural-prompt, full-media Codex rollout passes the numerical hardness and
long-horizon gates. The required `single_frame` and `no_media` shortcut checks
also pass; fresh Claude/Antigravity replacement-source runs remain pending.

| run | status | reward | notes |
|---|---:|---:|---|
| oracle | passed | 1.0 | Human-verified move sequence and result; 287/287 checks passed across 104 plies and 26 captures. |
| empty baseline | passed | 0.0 | Empty `moves` and `capture_events` submission; 0/287 checks passed. |
| Codex CLI (`codex-natural-chess-20260719T062119Z`) | passed | 0.0379 | Fresh GPT-5.6 Sol full-media rollout using the benchmark prompt with path-only rewriting; 13/343 checks, 45/104 plies, 17/26 captures, and 237 completed shell calls. The agent naturally exceeded 50 calls with no turn minimum or pacing hint. It wrote temporary analysis frames outside the workspace but did not access ground truth or public game data. |
| Codex CLI (`codex-replacement-chess-20260719T051110Z`) | diagnostic only | 0.0250 | Fresh GPT-5.6 Sol full-media rollout on the replacement source; 9/360 checks, 60/104 plies, 18/26 captures, and 142 completed shell calls. Its local prompt explicitly enforced the long-horizon minimum, so it remains audit evidence rather than acceptance calibration. |
| Claude Code CLI | pending | n/a | Needs fresh rollout on replacement source. Old `claude-local-chess-20260710T223658Z` result was against the retired source and must not be used for acceptance. |
| Antigravity CLI | pending | n/a | Needs fresh rollout on replacement source. Old `antigravity-local-chess-fixed-default-20260711T034259Z` result was against the retired source and must not be used for acceptance. |
| Codex single-frame ablation (`codex-ablation-single-frame-20260719T012741Z`) | passed | 0.0058 | GPT-5.6 Sol (high reasoning) received one representative frame from 00:13:00. It produced a plausible but incorrect 50-ply history and 8 captures; only 2/343 checks passed. |
| Codex no-media ablation (`codex-ablation-no-media-20260719T012741Z`) | passed | 0.0 | GPT-5.6 Sol (high reasoning) received only the prompt and schema, returned `unknown` with empty move/capture lists, and passed 0/287 checks. |

## Remaining Work

- The move sequence and Black-win result are verified. A second independent
  timestamp pass remains recommended for the +/- 6s annotations.
- Fresh Claude and Antigravity replacement-source runs remain pending as
  cross-agent confirmation; their retired-source scores do not count here.
