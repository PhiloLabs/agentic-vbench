# Ablations

Each ablation removes the video work and demands a best-effort answer anyway — a
model that declines to answer would measure nothing. Model: Claude Code CLI, Sonnet,
effort high, same instruction as the real task.

| ablation | inputs given | events submitted | score |
|---|---|---|---|
| no_media | instruction only | 15 | 0.0 |
| single_frame | one frame from the match midpoint | 11 | 0.0 |
| frame_dump | 60 uniform frames, no seeking | 22 | 0.0 |

`no_media` matters most here: this match's rally-by-rally log is public, so the
question is whether the answer can be recalled rather than watched. Forced to
answer, the model produced 15 plausible events and matched none — the per-event
score anchors and blocker/hitter pairs are not recallable.

Each `*.solution.json` is what the model submitted; each `*.reward.json` is the
scorer's output on it.
