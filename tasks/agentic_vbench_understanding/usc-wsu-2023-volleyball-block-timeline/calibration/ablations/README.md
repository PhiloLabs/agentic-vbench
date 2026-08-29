# Ablations

Each ablation removes the video work and demands a best-effort answer anyway — a
model that declines to answer would measure nothing. Model: Claude Code CLI, Sonnet,
effort high, same instruction as the real task.

| ablation | inputs given | tools | events submitted | score |
|---|---|---|---|---|
| no_media | instruction only | shell | 15 | 0.0 |
| single_frame | one frame from the match midpoint | shell | 11 | 0.0 |
| frame_dump | 60 uniform frames, no seeking | shell | 22 | 0.0 |
| all_frames | 80 stills, one every 90 s | Read, Write | 15 | 0.0 |

`all_frames` differs from `frame_dump` in what the model is allowed to do, not just
what it is given: the whole match is already in context as a uniform sweep, and the
shell is taken away, so there is no seeking, cropping, upscaling or scripting — only
opening an image and writing an answer.

Two conditions make that measurable rather than self-defeating. A model with no shell
and no directory listing cannot discover filenames, so all 80 are given in the prompt;
and the workspace lives outside the repository, so no judge, answer key or sibling run
is on a path it could open. `all_frames.instruction-as-run.md` is the exact prompt, and
the native trace is published with the other streams (`../scores.md`).

`no_media` matters most here: this match's rally-by-rally log is public, so the
question is whether the answer can be recalled rather than watched. Forced to
answer, the model produced 15 plausible events and matched none — the per-event
score anchors and blocker/hitter pairs are not recallable.

Each `*.solution.json` is what the model submitted; each `*.reward.json` is the
scorer's output on it.
