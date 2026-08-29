# Spec Card — usc-wsu-2023-volleyball-block-timeline

> Block-only timeline (service aces are excluded by design — see `scorer` note).

```yaml
task: agentic_vbench_understanding/usc-wsu-2023-volleyball-block-timeline

cognitive_level: understanding

modalities_required:
  video: the score bug says a point was scored — never why or by whom; classifying a
    rally ending as a block point (vs a kill driven through a block touch, or an
    attack error) and identifying both the blocker(s) and the stuffed hitter by
    jersey number inside a sub-second window at the net requires watching the play;
    college jerseys carry numbers, not names (roster provided)
  audio: not used (audio track stripped at bake time; the task is single-modality
    by construction, so commentary can never leak attributions)

question: Find every point that ended as a block, and report set, exact score after
  the point, the credited blocker(s), and the opposing hitter who was blocked.
output_schema: >
  {"events": [{"set": 1-5, "score_after": "USC-WSU digits", "type": "block",
  "players": ["First Last", ...], "blocked": "First Last"}]}. Scores increase
  monotonically within a set, so the exact score-after string anchors each event
  uniquely (this task's game clock); duplicates are handled by one-to-one multiset
  matching. Block credit follows the official scorer (one or two names,
  order-insensitive).

evidence:
  - 23 target block points hidden among ~200 rallies across five sets of a ~2h
    broadcast; finding them means triaging every score change
  - every target is a block point, so there is no legible "easy" event class — each
    one is a net exchange requiring TWO opposing jersey reads at the terminal instant
    (the credited blocker(s) AND the stuffed hitter), mapped through the roster
  - each TP chains the rally action with the score bug after it and the set context
    minutes away; the block window is under a second

ground_truth:
  source: official NCAA rally-by-rally log, stats.ncaa.org contest 3252428
  tier: machine-truth
  verification: reconciled per player against the official box score — Block Solos
    3 / 3, Block Assists 14 / 20, so team block points (BS + BA/2) come out 10 (USC)
    and 13 (WSU) = 23, matching the event list exactly. "Kill by X, Block by Y" rally
    lines (attacker kills through a block touch) are excluded as non-block points. No
    rally line is corrupted, so all 23 blocks carry a blocked hitter.

scorer:
  metric: two-tier F1 over block points — full credit (1.0) requires set, exact
    score_after, type, the exact blocker multiset AND the opposing hitter who was
    blocked; partial credit (0.5) when set, score_after, and type match and the
    credited names are off by exactly one. Names normalized (unambiguous-lastname
    rule — every GT lastname here is unique); greedy one-to-one matching, exact
    matches assigned first. Bar: a strong agent stays under ~0.10.
  design_note: service aces are excluded on purpose. An ace is a single legible
    jersey read with the ball landing untouched, and agents get them — in testing on
    this match a strong agent identified 4 of the 5 while getting no block right, and
    a handful of high-precision ace hits carries F1 on its own. Every target is
    instead a block point needing two opposing jersey reads at the net, so there is no
    legible easy class left to score off.
  oracle_reward: 1.0
  null_reward: 0.0 (measured; empty list)

difficulty:
  strong_agent_reward: Codex CLI (gpt-5.6-sol, xhigh) 0.0185; Claude Code (Opus 5,
    xhigh) 0.0. Both ran to completion in a fresh workspace and wrote their own
    answer; neither got a single block point fully correct. A Fable 5 run reached 210
    tool-call turns before that model's credit pool ran out; it is archived unscored,
    and resuming it with Opus 5 was tested and also scored 0.0, so it is not completed
    under another model's name.
  tool_call_turns: Codex 158 completed tool-call items; Opus 270 tool-call turns
    (both far above the 50 floor)
  agent_model: Codex CLI, Claude Code (Opus 5); Antigravity not run — on the sister
    BYU match its Gemini backends reconstruct the game from the public rally log
    unless three isolation vectors are applied at once

anti_shortcut:
  single_frame: 0.0 measured — one frame from the midpoint; the model was required to
    answer anyway and submitted 11 events, none correct
  video_only: n/a — the task ships video-only by construction
  audio_only: n/a — no audio track exists in the baked media
  no_media: 0.0 measured — instruction only. The NCAA rally-by-rally log for this
    match is public, so this is the leak that matters: forced to answer, the model
    submitted 15 plausible events and matched none
  frame_dump: 0.0 measured — 60 uniform frames, no seeking; 22 events submitted, none
    correct
  all_frames: 0.0 measured — the match as 80 stills, one every 90 s, with no shell at
    all: no seeking, cropping or scripting, only reading the frames. 15 events
    submitted, no rally anchor matched
  observability: calibration/observability/ shows the answer key IS visible in the
    video, but only in a 0.8-3.2 s net close-up after each point

input:
  url: https://huggingface.co/datasets/gavinlaw/agentic-vbench-media/resolve/7dc08d8a25c1192b411f586e60db6542776ae075/usc-wsu-2023-11-12-720p-noaudio.mp4
  dataset_revision: 7dc08d8a25c1192b411f586e60db6542776ae075
    (research re-host of the official WSU Athletics upload
    https://www.youtube.com/watch?v=RgJjVgi7rZY — provenance, rights and takedown
    policy documented in the dataset README)
  sha256: 13ccbabbdd9540da851099d138bef3c8eafe6de9426c3681593edba32d08ba9e
  length_min: 118.5 (measured 118.53; baked, audio stripped, single video stream)
  resolution: 720 (source stream is 1080p; baked at 720p, audio stripped)

score_order_note: score_after is written USC-WashingtonState (visitor-home), matching
  the broadcast score graphic (confirmed against the baked video: at t=60min the bug
  reads "13 USC | WSU 17" with USC on the left, matching GT set 3 score_after 13-17).
```
