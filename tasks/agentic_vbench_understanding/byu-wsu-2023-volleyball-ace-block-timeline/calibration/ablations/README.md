# Ablations

Each ablation removes the video work and demands a best-effort answer anyway — a
model that declines to answer would measure nothing. Model: Claude Code CLI, Sonnet,
effort high, same instruction as the real task.

| ablation | inputs given | events submitted | score |
|---|---|---|---|
| no_media | instruction only | 21 | 0.0 |
| single_frame | one frame from the match midpoint | 19 | 0.0 |
| frame_dump | 60 uniform frames, no seeking | 35 | 0.0 |

`no_media` is the one that matters most: this match's rally-by-rally log is public, so
the question is whether the answer can be recalled rather than watched. Forced to
answer, the model produced 21 plausible events and matched none — the per-event score
anchors and credited-player pairs are not recallable.

`frame_dump` submitted 35 events against a 24-event key and still scored zero, which
is the clearest statement of what uniform sampling buys here: it shows the match but
not the moments, and every rally ending it guessed at was wrong.

Each `*.solution.json` is what the model submitted; each `*.reward.json` is the
scorer's output on it.
