# Rollouts

Genuine calibration runs for the block-only USC task. Scores in `../scores.md` are
the block-only re-grades of these complete runs (see that file for why fresh
block-only re-runs were cut off by calibration infra, not the task).

- `codex-aceblock-run.solution.json` — Codex CLI (gpt-5.6-sol, xhigh), the full
  43-event answer from the genuine complete run (43 predicted, well over 50 tool-call
  turns; integrity: 0 answer-key refs, 0 web/grounding refs). Re-grades to **0.015**
  on the block-only judge (0 blocks fully correct, 1 partial).
- `fable-run.solution.json` — Claude Code (Fable 5, xhigh), the 9-event answer from
  the genuine run (finished after resuming a Max-session-limit interruption; ~597
  tool-call turns total; integrity: 0 answer-key refs, 0 web refs). Re-grades to
  **0.031** on the block-only judge (0 blocks fully correct, 1 partial).
- `fable-run.tool-histogram.txt` — digest of Fable's stream (435 tool-call turns in
  the first session: Read 280 for frames, Bash 146 for ffmpeg) in place of the raw
  ~300 MB stream-json.

Antigravity is not archived here — not independently re-run on this match; see the
Antigravity note in `../scores.md` for the sister-task isolation recipe that applies.

Both agents genuinely sampled the video (hundreds of ffmpeg frame reads) and neither
got a single block point fully correct — the blocker-multiset + stuffed-hitter net
attribution is the hard skill this task isolates.
