# Spec Card — byu-wsu-2023-volleyball-ace-block-timeline

```yaml
task: agentic_vbench_understanding/byu-wsu-2023-volleyball-ace-block-timeline

cognitive_level: understanding

modalities_required:
  video: the score bug says a point was scored — never why or by whom; classifying
    a rally ending (ace vs error, block point vs kill off the block) and identifying
    blockers by jersey number inside a sub-second window at the net requires
    watching the play; college jerseys carry numbers, not names (roster provided)
  audio: not used (audio track stripped at bake time; the task is single-modality
    by construction, so commentary can never leak attributions)

question: Find every point that ended as a service ace or a block, and report set,
  exact score after the point, event type, and the credited player(s).
output_schema: >
  {"events": [{"set": 1-4, "score_after": "BYU-WSU digits", "type": "ace"|"block",
  "players": ["First Last", ...]}]}. Scores increase monotonically within a set, so
  the exact score-after string anchors each event uniquely (this task's game clock);
  duplicates are handled by one-to-one multiset matching. Block credit follows the
  official scorer (one or two names, order-insensitive).

evidence:
  - 24 target events (5 aces, 19 block points) hidden among ~170 rallies across
    four sets of a ~2h broadcast; finding them means triaging every score change
  - each TP chains the rally action with the score bug after it and the set context
    minutes away; blocker identification requires jersey numbers glimpsed at the
    net mid-play, mapped through the provided roster (note BYU fields two Bowers,
    so a lastname alone is not enough)

ground_truth:
  source: official NCAA rally-by-rally log, stats.ncaa.org contest 3241315
  tier: machine-truth
  verification: reconciled per player against the official box score — every SA,
    block-solo, and block-assist column matches the event list exactly, and team
    block points (BS + BA/2) come out 8 (BYU) and 11 (WSU); one rally line whose
    name field contradicts the box score is resolved in favor of the box-score
    credit (set 2 at 1-2, a Jehlarova solo block)

scorer:
  metric: two-tier F1 over events — full credit (1.0) requires set, exact
    score_after, type, and the exact credited-player multiset; partial credit (0.5)
    when set, score_after, and type match and the credited players differ by exactly
    one name (block credit is a stats-crew ruling a perfect visual agent can miss).
    Names normalized (unambiguous-lastname rule); greedy one-to-one matching with
    exact matches assigned first, so duplicate anchors are consumed at most once
  oracle_reward: 1.0
  null_reward: 0.0 (measured; empty list)

difficulty:
  strong_agent_reward: TBD (to be measured, target < 0.10)
  tool_call_turns: TBD (to be measured, target > 50)
  agent_model: Antigravity, Codex CLI, Claude Code CLI (per family requirements)

anti_shortcut:
  single_frame: ~0 expected — no graphic ever lists aces or blocks; one frame shows
    one rally at most (to be measured)
  video_only: n/a — the task ships video-only by construction
  audio_only: n/a — no audio track exists in the baked media
  no_media: ~0 expected — ordinary early-season college match; the exact per-event
    score anchors and credited-player pairs are unguessable (to be measured)
  frame_dump_no_tools: ~0 expected — a block window is under a second; uniform
    frames miss it, and rally-end classification needs targeted dense sampling
    (to be measured)

input:
  url: https://huggingface.co/datasets/gavinlaw/agentic-vbench-media/resolve/main/byu-wsu-2023-09-08-720p-noaudio.mp4
    (research re-host of the official WSU Athletics upload
    https://www.youtube.com/watch?v=5KC1jC90lT8 — provenance, rights and takedown
    policy documented in the dataset README)
  sha256: ee887b18cf3dc9afce05087b24b629d1c44433344d7d4ccf612a4e548796dc60
  length_min: 115 (measured 114.9)
  resolution: 720 (source stream is 1080p; baked at 720p, audio stripped)
```
