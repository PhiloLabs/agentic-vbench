# Calibration Scores

This task is in post-review revision. The source has been replaced, and the new
104-ply move sequence and Black-win result have been human-verified. A fresh
natural-prompt, full-media Codex rollout passes the numerical hardness and
long-horizon gates. The required `single_frame` and `no_media` shortcut checks
also pass. A fresh Claude attempt hit its subscription limit before submission.
A fresh checkpoint-assisted Antigravity run produced a scored submission, but a
completed Claude rerun and natural-prompt Antigravity run remain pending if
clean cross-agent confirmation is required.

| run | status | reward | notes |
|---|---:|---:|---|
| oracle | passed | 1.0 | Human-verified move sequence and result; 287/287 checks passed across 104 plies and 26 captures. |
| empty baseline | passed | 0.0 | Empty `moves` and `capture_events` submission; 0/287 checks passed. |
| Codex CLI (`codex-natural-chess-20260719T062119Z`) | passed | 0.0379 | Fresh GPT-5.6 Sol full-media rollout using the benchmark prompt with path-only rewriting; 13/343 checks, 45/104 plies, 17/26 captures, and 237 completed shell calls. The agent naturally exceeded 50 calls with no turn minimum or pacing hint. It wrote temporary analysis frames outside the workspace but did not access ground truth or public game data. |
| Codex CLI (`codex-replacement-chess-20260719T051110Z`) | diagnostic only | 0.0250 | Fresh GPT-5.6 Sol full-media rollout on the replacement source; 9/360 checks, 60/104 plies, 18/26 captures, and 142 completed shell calls. Its local prompt explicitly enforced the long-horizon minimum, so it remains audit evidence rather than acceptance calibration. |
| Claude Code CLI (`claude-natural-chess-20260719T070702Z`) | incomplete; rerun pending | 0.0 | Fresh Sonnet 5 high-effort attempt using the benchmark prompt with path-only rewriting. It naturally reached 210 completed tool uses (212 native turns) in 40m50s, then hit API 429 session limit before writing `solution.json`; 0/287 checks passed because the submission was missing. It installed generic `python-chess` with `pip` and wrote two frame-name lists under `/tmp`, but made no web searches and did not access ground truth. |
| Antigravity CLI (`antigravity-checkpoint-chess-20260719T162817Z`) | completed; checkpoint-assisted diagnostic | 0.0205 | Fresh Gemini 3.5 Flash (Medium) run on the replacement source. The canonical initial prompt used path-only rewriting, but the external wrapper sent checkpoint requests after 45 and 51 calls. It wrote 8/104 plies and 1/26 captures at 53 calls, passing 6/292 checks, then stopped because the score was below 0.5; the 75-call cap was not approached. It installed `python-chess` and OpenCV with pip, including a downloaded NumPy wheel, so this is not clean natural-prompt calibration. |
| Codex single-frame ablation (`codex-ablation-single-frame-20260719T012741Z`) | passed | 0.0058 | GPT-5.6 Sol (high reasoning) received one representative frame from 00:13:00. It produced a plausible but incorrect 50-ply history and 8 captures; only 2/343 checks passed. |
| Codex no-media ablation (`codex-ablation-no-media-20260719T012741Z`) | passed | 0.0 | GPT-5.6 Sol (high reasoning) received only the prompt and schema, returned `unknown` with empty move/capture lists, and passed 0/287 checks. |

## Remaining Work

- The move sequence and Black-win result are verified. A second independent
  timestamp pass remains recommended for the +/- 6s annotations.
- A completed post-reset Claude run remains pending. The replacement-source
  Antigravity run is complete as checkpoint-assisted evidence; a clean natural
  run remains pending if natural cross-agent confirmation is required. Neither
  retired-source scores nor the quota-truncated Claude attempt count as
  completed natural calibration.
