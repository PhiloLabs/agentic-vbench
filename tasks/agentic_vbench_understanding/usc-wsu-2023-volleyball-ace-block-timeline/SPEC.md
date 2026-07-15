# Spec Card — usc-wsu-2023-volleyball-ace-block-timeline

```yaml
task: agentic_vbench_understanding/usc-wsu-2023-volleyball-ace-block-timeline

cognitive_level: understanding

modalities_required:
  video: the score bug says a point was scored — never why or by whom; classifying
    a rally ending (ace vs error, block point vs kill driven through a block touch)
    and identifying blockers by jersey number inside a sub-second window at the net
    requires watching the play; college jerseys carry numbers, not names (roster
    provided)
  audio: not used (audio track stripped at bake time; the task is single-modality
    by construction, so commentary can never leak attributions)

question: Find every point that ended as a service ace or a block, and report set,
  exact score after the point, event type, and the credited player(s) (plus, for a
  block, the opposing hitter who was blocked).
output_schema: >
  {"events": [{"set": 1-5, "score_after": "USC-WSU digits", "type": "ace"|"block",
  "players": ["First Last", ...], "blocked": "First Last" (block only)}]}. Scores
  increase monotonically within a set, so the exact score-after string anchors each
  event uniquely (this task's game clock); duplicates are handled by one-to-one
  multiset matching. Block credit follows the official scorer (one or two names,
  order-insensitive).

evidence:
  - 28 target events (5 aces, 23 block points) hidden among ~200 rallies across five
    sets of a ~2h broadcast; finding them means triaging every score change
  - heavily block-dominant (only 5 aces in the whole match, versus 23 block points),
    so almost every target is a net exchange rather than an easy-to-read serve
  - each TP chains the rally action with the score bug after it and the set context
    minutes away; blocker identification requires jersey numbers glimpsed at the net
    mid-play, mapped through the provided roster, and the blocked hitter is a second
    jersey read, on the opposing team, at the same terminal instant

ground_truth:
  source: official NCAA rally-by-rally log, stats.ncaa.org contest 3252428
  tier: machine-truth
  verification: reconciled per player against the official box score — aces USC 1 /
    WSU 4, Block Solos 3 / 3, Block Assists 14 / 20, so team block points
    (BS + BA/2) come out 10 (USC) and 13 (WSU); every SA, block-solo, and
    block-assist column matches the event list exactly. "Kill by X, Block by Y"
    rally lines (attacker kills through a block touch) are excluded as non-block
    points. No rally line is corrupted, so all 23 blocks carry a blocked hitter.

scorer:
  metric: two-tier F1 over events — full credit (1.0) requires set, exact
    score_after, type, and every credited name (for a block: the exact blocker
    multiset AND the opposing hitter who was blocked); partial credit (0.5) when
    set, score_after, and type match and the credited names are off by exactly one
    (block credit and reading the stuffed hitter's number are stats-crew/visual
    judgments a perfect agent can miss). Names normalized (unambiguous-lastname
    rule — every GT lastname here is unique); greedy one-to-one matching, exact
    matches assigned first. Bar: a strong agent stays at/under ~0.10 (reviewer
    accepts <= 0.109).
  oracle_reward: 1.0
  null_reward: 0.0 (measured; empty list)

difficulty:
  strong_agent_reward: TBD (to be measured, target < 0.10)
  tool_call_turns: TBD (to be measured, target > 50)
  agent_model: Antigravity, Codex CLI, Claude Code CLI (per family requirements)
  note: sister task byu-wsu-2023-volleyball-ace-block-timeline (same structure, same
    home broadcast production) measured Codex CLI 0.02 and Claude Code (Fable) 0.15;
    this match is more block-dominant (23 blocks / 5 aces vs 19 / 5), so a similar
    or lower band is expected.

anti_shortcut:
  single_frame: ~0 expected — no graphic ever lists aces or blocks; one frame shows
    one rally at most (to be measured)
  video_only: n/a — the task ships video-only by construction
  audio_only: n/a — no audio track exists in the baked media
  no_media: ~0 expected — ordinary regular-season college match; the exact per-event
    score anchors and credited-player pairs are unguessable (to be measured)
  frame_dump_no_tools: ~0 expected — a block window is under a second; uniform
    frames miss it, and rally-end classification needs targeted dense sampling
    (to be measured)

input:
  url: https://huggingface.co/datasets/gavinlaw/agentic-vbench-media/resolve/main/usc-wsu-2023-11-12-720p-noaudio.mp4
    (research re-host of the official WSU Athletics upload
    https://www.youtube.com/watch?v=RgJjVgi7rZY — provenance, rights and takedown
    policy documented in the dataset README)
  sha256: PENDING_BAKE_UPLOAD (set after environment/bake_media.sh + dataset upload)
  length_min: ~118.5 (source runtime 1:58:32; confirm on baked file)
  resolution: 720 (source stream is 1080p; baked at 720p, audio stripped)

score_order_note: score_after is written USC-WashingtonState (visitor-home), matching
  the broadcast score graphic. This mirrors the sister BYU task convention (visitor
  on the left); confirm the on-screen bug orientation against the baked video during
  calibration, as was done for BYU.
```
