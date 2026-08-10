---
title: Task Spec Card
summary: kart-race-telemetry-ledger-s1 — count the camera-followed hero kart's powerup pickups, explosions and banana hits across twelve AI-driven SuperTuxKart races, and rank the races by each.
---

# Task Spec Card

```yaml
task: agentic_vbench_understanding/kart-race-telemetry-ledger-s1

cognitive_level: understanding
# The camera is a chase-cam locked to one hero kart (tux) for the whole suite. For each of twelve
# races the agent counts THREE off-HUD quantities for the hero — powerup boxes driven through,
# times blown up, and bananas hit — none shown as a number. Fine-grained event counting over a
# ~53-min horizon, then a cross-race ranking per quantity. The ranking column and minimap are
# navigation aids, never answers.

modalities_required:
  video: the hero, its HUD powerup slot, the ranking column and minimap are all visual.
  audio: not used.

question: For each race, count the HERO kart's powerup boxes, explosions and banana hits (the three off-HUD quantities), reported in race order.
output_schema: '{"races": [{"track": str, "items_collected": int, "times_exploded": int, "bananas_hit": int}]}'  # nitro/positions optional, unscored

ground_truth:
  source: SuperTuxKart 1.5 profile mode (--profile-laps) result table; the AI drives every kart
          and STK prints the exact per-kart telemetry. The camera follows the hero because the
          generator makes it the player kart (--kart=tux --ai=<rest>), so the recorded run is its
          own ground truth AND the scored kart is on screen the whole race.
  tier: machine-truth
  verification: oracle solution.json = the hero's profile rows; judge.py scores it 1.0 through the
                harness path (solve.sh -> judge.py): 12 races, items tau 1.0 (59 pairs),
                explosions tau 1.0 (52 pairs), bananas tau 1.0 (49 pairs).

scorer:
  metric: "max(0, [0.40*tau(items) + 0.30*tau(explosions) + 0.30*tau(bananas)] renormalised over
           the fields that vary in the GT); tau = SIGNED normalised Kendall correlation over the
           RACES, ordered by the hero's count. Renormalising lets the oracle reach 1.0 even if a
           field is flat."
  oracle_reward: 1.0
  null_reward: 0.0
  measured_ablations:          # on the shipped 12-race ground truth
    blind_guess: 0.063         # 400 random-count solutions; mean 0.063, p95 0.26
    constant_counts: 0.0       # every race given the same count -> all predicted ties -> 0
    empty: 0.0
    perfect_items_only: 0.40   # perfect items ranking, nothing else — a single-quantity agent caps here
    perfect_items+explosions: 0.70   # two of three quantities perfect — you must also count bananas
  # HONEST DIFFICULTY NOTE. The task was first rewritten to fix the observability flaw the reviewer
  # flagged (STK's chase-cam shows one kart, so ranking all twelve was unobservable); scoping to the
  # single camera-followed hero fixed fairness but made it easy (perfect items alone ~0.51 on the
  # first 8x3 cut). This version HARDENS it within that fair frame: 12 races x 4 laps (~53 min, so a
  # recall-limited agent that skims miscounts more), THREE independent off-HUD counts instead of two
  # (items 0.40 / explosions 0.30 / bananas 0.30 — a one-quantity agent now caps at 0.40, and even
  # two-of-three caps at 0.70), and a tighter guess floor (12 races = 59 item-pairs -> blind mean
  # 0.063, p95 0.26, down from 0.086 / 0.40). It remains a FAIR, MEDIUM entry — strict <0.10 is not
  # reached by any counting task here (the sibling Minecraft ordered-ledger is 0.164). A true
  # ordered-ledger (harder) would need machine-exact per-event ORDER; STK's prebuilt binary exposes
  # only per-race COUNTS (no headless race-replay recording, and the replay format logs no pickup /
  # explosion events), so counts are the ceiling for this engine.

difficulty: {strong_agent_reward: recalibrating, tool_call_turns: TBD, agent_model: codex gpt-5.6-sol xhigh}
# HARDER VARIANT (HUD powerup slot masked). On the UN-masked 12-race suite Codex scored 0.407
# (items tau 0.64, explosions 0.54, bananas -0.04; rollout calibration/rollouts/codex_12x4_*). This
# shipped video MASKS the top-center HUD powerup indicator, so the agent loses the pickup
# confirmation and must catch each item from the hero driving through a box — expected to lower the
# items term further. Masked-variant calibration is re-running (calibration/rollouts/codex_masked_*).
# For reference, the un-masked run: per-field tau items 0.64, explosions 0.54, bananas -0.04 — a fair medium result,
# above the family's <0.10 ideal but in line with its honest-medium practice (the sibling Minecraft
# ordered-ledger is 0.164).

anti_shortcut:
  single_frame: one frame gives one instantaneous ranking, not twelve races' worth of counts.
  no_media: the twelve per-race counts are not knowable blind — measured blind-guess mean 0.063.
  frame_dump_no_tools: a 53-min video at 1 fps is >3000 frames, past any context window, so an
    agent cannot ingest it without seeking tools.

input:
  url: https://huggingface.co/datasets/explcre/agenticvbench-understanding-materials/resolve/main/kart-race-telemetry-ledger-s1/race.mp4
  sha256: a84170a13f0d8392e18a0fd0535e5ddad7ceae4888d5c826b6b77850f78bf322
  length_min: 53.4
  resolution: 720
  contents: 12 races (hacienda, snowmountain, cornfield_crossing, lighthouse, gran_paradiso_island,
            sandtrack, olivermath, cocoa_temple, scotland, fortmagma, ravenbridge_mansion,
            stk_enterprise), 4 laps each, 10-kart fields on SuperTux (hardest) AI. The hero (tux) is
            in every race and the camera follows it throughout; the TOP-CENTER HUD powerup slot is
            MASKED (black box) so pickups must be counted from the hero driving through a box, not
            from a HUD confirmation; the other nine race around it
            (contesting boxes, bombing it) for realism. (black_forest was dropped — its dense
            foliage renders in slow-motion under software GL.)
```

## Notes

- **Why it is a real reconstruction problem.** The hero's pickups, explosions and banana hits are
  shown nowhere as a number; recovering them means following the hero through every lap of every
  race and counting three kinds of discrete event, then ordering the twelve races by each tally. On
  SuperTux difficulty the hero is genuinely bombed and fights for boxes, so the counts are non-trivial.
- **Observability is the point.** Because the camera is locked to the hero and only the hero is
  scored, every scored event is on screen by construction — no off-camera pickup caps the score.
- **Rank-agreement scoring is deliberate.** Kendall tau over the races keeps the guessing floor
  near 0 (concordant and discordant race-pairs cancel) while granting partial credit for a partial
  ordering. Ground-truth ties are excluded from tau's numerator and denominator so the oracle is 1.0.

## Fairness constraint enforced during generation

- **The hero is always present and always the camera target.** run_race.sh passes
  `--kart=<hero> --ai=<rest>`; build_ground_truth.py asserts the hero appears in every race's
  parsed field and that the primary scored field (items) varies across races, or it refuses to
  emit a degenerate ground truth.
- **The field stays legible.** parse_profile.py asserts the parsed field size and rejects
  duplicate kart ids (STK silently backfills an unknown `--ai` id with a duplicate), so every kart
  on track is a distinct visible character.

## Known limitations

- The ceiling is counting, not ordered reconstruction: STK's prebuilt binary gives per-race counts
  but not machine-exact per-event order, so this stays a fair MEDIUM task rather than sub-0.10.
- rescues are witnessable (the lift-back) but the SuperTux AI rarely falls, so that column is
  near-constant and is reported for context, not scored.
