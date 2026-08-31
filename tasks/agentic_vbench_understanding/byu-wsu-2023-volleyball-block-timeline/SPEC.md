# Spec Card — byu-wsu-2023-volleyball-block-timeline

> Block-only timeline requiring three attributions per point.

```yaml
task: agentic_vbench_understanding/byu-wsu-2023-volleyball-block-timeline

cognitive_level: understanding

modalities_required:
  video: the score bug says a point was scored — never why or by whom; classifying
    a rally ending (block point vs a kill driven through a block touch vs an attack
    error) and identifying the players by jersey number inside a sub-second window at
    the net requires watching the play; college jerseys carry numbers, not names
    (roster provided)
  audio: not used (audio track stripped at bake time; the task is single-modality
    by construction, so commentary can never leak attributions)

question: Find every point that ended as a block, and report set, exact score after
  the point, the credited blocker(s), the opposing hitter who was blocked, and the
  setter who fed that attack.
output_schema: >
  {"events": [{"set": 1-4, "score_after": "BYU-WSU digits", "type": "block",
  "players": ["First Last", ...], "blocked": "First Last", "setter": "First Last"}]}.
  Scores increase monotonically within a set, so the exact score-after string anchors
  each event uniquely; duplicates are handled by one-to-one multiset matching. Block
  credit follows the official scorer (one or two names, order-insensitive).

evidence:
  - 18 block points scattered across four sets of a ~2 h broadcast; finding them means
    triaging every score change
  - each point needs THREE attributions, not one: the credited blocker(s) at the net,
    the opposing hitter they stopped, and the setter who fed that hitter earlier in
    the same rally. The first two are opposing jerseys at the terminal instant; the
    third sits mid-rally, before the attack, so it cannot be read off the post-point
    close-up and has to be tracked back through the rally
  - college jerseys carry numbers, not names, so every read goes through the roster

ground_truth:
  source: official NCAA rally-by-rally log, stats.ncaa.org contest 3241315
  tier: machine-truth
  verification: reconciled per player against the official box score — every block
    solo and block assist column matches, and team block points (BS + BA/2) come out
    8 (BYU) and 11 (WSU), 19 in total. 18 are in the key: one rally line (set 2 at
    1-2, a WSU block point) is corrupted in the raw log — its name field credits a
    blocker on the scoring team's opponent, and neither the stuffed hitter nor the
    setter survives — so it carries no answerable attribution and is left out. Finding
    it is correct play, so the scorer sets a prediction anchored there aside: it earns
    nothing and costs nothing, and `test_judge.py` pins that. The key holds every block
    point the official record fixes unambiguously.

scorer:
  metric: two-tier F1 over block points — full credit (1.0) requires set, exact
    score_after, the exact blocker multiset, the blocked hitter AND the setter;
    partial credit (0.5) when exactly one of those three attributions is wrong. Name
    errors are counted as max(unmatched-key, unmatched-prediction), so a substitution
    is one error whether the block was solo or shared. Names normalized (unambiguous-
    lastname rule, computed over blockers, hitters and setters alike, so the two
    Bowers stay distinct); greedy one-to-one matching, exact matches assigned first.
    Bar: a strong agent stays under ~0.10.
  design_note: the three attributions are deliberately not equally reachable. The
    blocker(s) and the stuffed hitter are both at the net at the terminal instant,
    where the broadcast cuts to a close-up, so an agent that finds that window reads
    them together; the setter touched the ball seconds earlier, mid-rally, in the wide
    shot, and can only be recovered by tracking the rally back from its ending. With
    only 18 events, full credit has to be that hard to earn or a couple of lucky reads
    dominate the score. On the two calibration answers the setter requirement costs
    nothing — both miss the net attribution as well (see calibration/scores.md).
  oracle_reward: 1.0
  null_reward: 0.0 (measured; empty list)

difficulty:
  strong_agent_reward: measured inside the shipped task image, where every action on
    the video runs in a container built from environment/Dockerfile with no network —
    Codex CLI (gpt-5.6-sol, xhigh) 0.0952; Claude Code (Opus 5, xhigh) 0.0. Codex
    matched 11 of the 18 rally anchors from 24 submitted events and got one block point
    fully correct (set 1 at 18-14: both blockers, the hitter and the setter); Opus
    submitted 8 and matched one anchor. The same agents on the calibration host scored
    0.0213 and 0.0; see calibration/parity/.
  tool_call_turns: in the task image, Opus 384 tool-call turns (231 Read, 152 Bash);
    on the host, Codex 71 completed items and Opus 386 turns (all far above the 50
    floor)
  agent_model: Codex CLI, Claude Code (Opus 5); Antigravity not run — its Gemini
    backends ground against the public rally log unless three isolation vectors are
    applied at once (evidence in calibration/agent-integrity/)

anti_shortcut:
  single_frame: measured — one frame from the match midpoint, model required to
    answer anyway
  video_only: n/a — the task ships video-only by construction
  audio_only: n/a — no audio track exists in the baked media
  no_media: measured — instruction only. This match's rally-by-rally log is public,
    so this is the leak that matters: the model answers from recall and matches
    nothing
  frame_dump: measured — 60 uniform frames, no seeking
  all_frames: measured — the match as 77 stills, one every 90 s, with no shell at
    all: no seeking, cropping or scripting, only reading the frames
  (see calibration/scores.md for the submitted-event counts and scores)

input:
  url: https://huggingface.co/datasets/gavinlaw/agentic-vbench-media/resolve/7dc08d8a25c1192b411f586e60db6542776ae075/byu-wsu-2023-09-08-720p-noaudio.mp4
  dataset_revision: 7dc08d8a25c1192b411f586e60db6542776ae075
    (research re-host of the official WSU Athletics upload
    https://www.youtube.com/watch?v=5KC1jC90lT8 — provenance, rights and takedown
    policy documented in the dataset README)
  sha256: ee887b18cf3dc9afce05087b24b629d1c44433344d7d4ccf612a4e548796dc60
  length_min: 115 (measured 114.9)
  resolution: 720 (source stream is 1080p; baked at 720p, audio stripped)
```
