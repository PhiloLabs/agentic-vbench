---
title: Task Spec Card
summary: minecraft-gameplay-ledger-s1 — reconstruct a player's timed action ledger, with the weapon used per kill, from a first-person Minecraft session.
---

# Task Spec Card

```yaml
task: agentic_vbench_understanding/minecraft-gameplay-ledger-s1

cognitive_level: understanding
# Follow a moving first-person session across eight biomes and reconstruct the ordered, TIMED
# sequence of deliberate actions — 1995 actions over ~238 minutes — including the weapon used for
# each kill and roughly WHEN each action happens. Every recorded action is on-camera by construction.

modalities_required:
  video: the action sequence exists only across frames of the first-person view.
  audio: not used.

question: Reconstruct the player's ordered action ledger with video times (mine/place block-type, kill mob-type + weapon).
output_schema: '{"events": [{"action": "mine"|"place"|"kill", "target": <block/mob>, "tool": "sword"|"bow", "t": <video seconds>}]}'

ground_truth:
  source: the mineflayer bot's own events (dig completion, entity death) plus its own
          /setblock placements; Paper 1.16.5 generated world. Each event carries its video time t.
  tier: machine-truth
  verification: oracle solution.json = the bot's ordered ledger with true times; judge.py scores it 1.0.

scorer:
  metric: "0.85 * F2 (recall-weighted, beta=2) over ordered (action,target) + 0.15 * weapon score
           over aligned kills (the 0.15 weapon weight applies only when the render has kills to
           score - v38 has 139 - else it folds into F2, so the oracle is 1.0 for any render).
           Alignment is an order-preserving longest-common-subsequence on
           (action,target) with a TIME WINDOW: a predicted event aligns to a ground-truth event only
           if its time t is within +/-10 s of the true video time. Gap-tolerant (one miss/extra/wrong
           event costs only that event); the time window makes the order real."
  oracle_reward: 1.0
  null_reward: 0.0
  measured_ablations:       # same GT, deliberately wrong submissions, under the shipped scorer
    shuffled_ledger: 0.043  # right multiset, order shuffled — LCS order + time window defeat it
    wrong_times: 0.008      # right multiset, random times — the time window defeats it
    single_token_xN: 0.047  # most common (action,target) repeated, times spread evenly
    targets_wrong: 0.019    # actions + times right, every target replaced by "stone"

difficulty:
  strong_agent_reward: 0.020   # Codex gpt-5.6-sol (xhigh) on the shipped v38 under the timestamp metric
                               # (two runs: 0.0196 / 0.0105); rollout -> calibration/rollouts/codex_v38ts_*
  agent_model: "codex gpt-5.6-sol, model_reasoning_effort=xhigh"
  note: "MEETS the family's strong-agent < 0.10 bar, by a wide margin. The +/-10 s time window makes
         the task strictly no easier than the order-only 0.070; in practice the agent under-engages
         when it must also localise ~2000 events in a 238-min video, reconstructing ~70-100 events
         (vs 194 order-only) and landing few within the window, so reward is ~0.01-0.02 (n=2,
         run-dependent). Difficulty is recall + time-localisation limited; event count/density is the
         lever, not a metric hack (oracle=1.0, shuffled 0.043)."

anti_shortcut:
  single_frame: 0.0             # Codex given one mid-video frame: correctly wrote an empty ledger
  most_common_token_xN: 0.047   # the single commonest (action, target), repeated, times spread
  actions_right_targets_stone: 0.019
  correct_multiset_shuffled: 0.043   # order shuffled, true times kept — order+window defeat it
  correct_multiset_wrong_times: 0.008
  empty: 0.0
  frame_dump_no_tools: 0.0      # a 238-min video at 1 fps is >14000 frames, far past any context window

input:
  url: https://huggingface.co/datasets/explcre/agenticvbench-understanding-materials/resolve/39f1b933102acb3e52348752eb736b31c4c9d50b/minecraft-gameplay-ledger-s1/game_v38.mp4
  sha256: 110f1232d516f0649b3181858d845afba643a07948b4c84c346f8a82d1b0e60a
  length_min: 238.5
  resolution: 720
  contents: 1995 events (355 mine, 1501 place, 139 kill); 41 distinct block/mob types; biomes forest,
            beach, desert, snowy tundra, jungle, plains, savanna, badlands (x9 laps, re-rolled
            palettes); 27 structures built on camera (cabin with a full gable roof whose timber
            rotates per lap, village well, watchtower) + a staircase mine through layered strata.
            Every recorded event is guaranteed on-camera (see fairness constraints). The SAME
            generator scales to any length: 628-event 53-min and 248-event 19-min instances also exist.
```

## Notes

- **Real first-person gameplay** — a moving player, real mining with the camera turning to
  each block, sword and bow combat, and structures assembled block by block. Real-life
  analog: gameplay/instructional-video analysis and embodied-agent behaviour verification.
  Distinct from VPT/MineRL frame-level inverse dynamics: this is long-horizon and
  event-level, not per-frame action regression.
- **Order + time scoring.** The ground truth is the bot's own event order, each event tagged with its
  video time `t` (seconds from the start of the graded video). A submission is aligned by a gap-
  tolerant, order-preserving LCS on the `(action, target)` tokens, and a match is allowed only when
  the predicted `t` is within **±10 s** of the true time. The window is wide enough to absorb the
  agent's time-reading imprecision and the software render's timing jitter (the video-time↔event-time
  map was verified accurate at both ends of the 238-min video) yet far tighter than the span, so a
  ledger with the right blocks but the wrong timing cannot score.
- **The HUD is the real game HUD, and it is evidence.** It is composited from the actual Minecraft GUI
  sprites shipped with prismarine-viewer at vanilla geometry. The highlighted slot tracks the item the
  player actually held, from the bot's own held-item timeline, so the weapon component is answerable.
  Two effects the renderer omits are composited back from the event log: a red hit-flash marks each
  kill, and the vanilla block-break crack grows over each dig. The crack is **projected onto the mined
  block's exact screen position** from the camera pose recorded at the swing (pinhole, the viewer's
  real 75-deg FOV), scaled by distance, so it sits ON the block. The sprite is the real vanilla texture.

## Fairness constraints enforced during generation

Each would otherwise put unanswerable rows into the ground truth.

1. **Only mobs this renderer actually draws are in the vocabulary.** An audit of 27 mobs found 11
   render (`generator/MOB_RENDER_AUDIT.md`); invisible mobs are excluded.
2. **Every scored kill was witnessed.** A kill is recorded only if the mob was present and in range
   for several consecutive attack ticks with the camera on it. In the shipped v38 session 86 attempted
   kills were rejected by this gate (off-camera) and 139 recorded.
3. **Every scored action is framed dead-centre, not merely on screen.** The viewer's vertical FOV is
   75 deg, so a block more than ~24 deg off the view axis is at the frame edge. Before each placement
   the bot moves to a vantage at the block's OWN height — using creative flight for high courses like
   the roof — backed off along the block's outward normal, and aims the camera dead-centre with clear
   line of sight; a block that cannot be framed that way from any vantage is **skipped entirely —
   neither placed nor recorded** (33 in v38), so the world and the ledger stay identical. Mines are
   framed the same way and the camera settles on the block through the full crack window before the dig.
4. **No blind-guessable runs.** Build palettes alternate within each layer and the roof timber rotates
   per lap (oak / spruce / birch / jungle / acacia), so the most-common (action, block) token is 6.9%
   of the ledger and the single-token shortcut is 0.047.
5. **Every structure is verified visible.** The generator raycasts to each finished build and checks
   the first block hit belongs to it (`ORBIT_SHOWN n/m`); all 27 structures were shown in v38.

## Known limitations

- **The task is a HARD long-horizon task, and the video is long (238 min).** The strong-agent score is
  driven down by event count (recall-limited); the generator trades render/eval time for difficulty.
  The same generator emits shorter, easier instances (a 53-min / 628-event build scores ~0.36).
- **Weapon credit is gated on ledger alignment.** With only two weapon classes, scored independently
  it was nearly free; credit is now granted only on kills inside the alignment. The oracle stays 1.0.
- **Spurious air-mines are dropped.** A shaft cut that resolves to `air`/`cave_air` is not a nameable
  block; both the generator's `rec()` and the GT builder drop it (0 in v38).
- The video-time↔event-time map is treated as accurate to within the ±10 s scoring window; it was
  spot-checked at ~2.5 min and ~210 min into the video (events appear at their predicted times). A
  grader reading times off the video hits the window comfortably; the oracle uses the true times.
