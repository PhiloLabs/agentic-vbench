# Spec Card — byu-wsu-2023-volleyball-ace-block-timeline

> Block-only timeline requiring three attributions per point. The directory keeps its
> original `ace-block` slug so the open PR survives; the task ID should be renamed to
> `byu-wsu-2023-volleyball-block-timeline` before merge.

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
    third sits mid-rally, before the attack, and has to be tracked back to
  - college jerseys carry numbers, not names, so every read goes through the roster

ground_truth:
  source: official NCAA rally-by-rally log, stats.ncaa.org contest 3241315
  tier: machine-truth
  verification: reconciled per player against the official box score — every SA,
    block-solo, and block-assist column matches the event list exactly, and team
    block points (BS + BA/2) come out 8 (BYU) and 11 (WSU); one rally line whose
    name field contradicts the box score is resolved in favor of the box-score
    credit (set 2 at 1-2, a Jehlarova solo block)

scorer:
  metric: two-tier F1 over block points — full credit (1.0) requires set, exact
    score_after, the exact blocker multiset, the blocked hitter AND the setter;
    partial credit (0.5) when exactly one of those three attributions is wrong. Names
    normalized (unambiguous-lastname rule, computed over blockers, hitters and setters
    alike, so the two Bowers stay distinct); greedy one-to-one matching, exact matches
    assigned first. Bar: a strong agent stays under ~0.10.
  oracle_reward: 1.0
  null_reward: 0.0 (measured; empty list)

difficulty:
  strong_agent_reward: Codex CLI (gpt-5.6-sol, xhigh) 0.0189; Claude Code (Opus 5,
    xhigh) 0.0. Both ran fresh on the final three-attribution instruction in clean
    workspaces, wrote their own answers, and got no block point fully correct.
  tool_call_turns: Codex 29-event answer over a 146 KB rollout; Opus 386 tool-call
    turns (both far above the 50 floor)
  agent_model: Codex CLI, Claude Code (Opus 5); Antigravity not run — its Gemini
    backends ground against the public record unless the three-vector isolation
    recipe from this task's earlier calibration is applied

anti_shortcut:
  single_frame: measured — one frame from the match midpoint, model required to
    answer anyway
  video_only: n/a — the task ships video-only by construction
  audio_only: n/a — no audio track exists in the baked media
  no_media: measured — instruction only. This match's rally-by-rally log is public,
    so this is the leak that matters: the model answers from recall and matches
    nothing
  frame_dump: measured — 60 uniform frames, no seeking
  (see calibration/scores.md for the submitted-event counts and scores)

input:
  url: https://huggingface.co/datasets/gavinlaw/agentic-vbench-media/resolve/859cb6877dc31b75d336648c4d3c87509e3373ab/byu-wsu-2023-09-08-720p-noaudio.mp4
  dataset_revision: 859cb6877dc31b75d336648c4d3c87509e3373ab
    (research re-host of the official WSU Athletics upload
    https://www.youtube.com/watch?v=5KC1jC90lT8 — provenance, rights and takedown
    policy documented in the dataset README)
  sha256: ee887b18cf3dc9afce05087b24b629d1c44433344d7d4ccf612a4e548796dc60
  length_min: 115 (measured 114.9)
  resolution: 720 (source stream is 1080p; baked at 720p, audio stripped)
```
