---
title: Task Spec Card
summary: kart-race-telemetry-ledger-s1 — count each kart's powerup-box pickups across six AI-driven 12-kart SuperTuxKart races.
---

# Task Spec Card

```yaml
task: agentic_vbench_understanding/kart-race-telemetry-ledger-s1

cognitive_level: understanding
# Follow twelve karts through each of six races on different tracks and count how many powerup
# boxes each of them drove through. That total is shown nowhere on screen, so this is
# fine-grained event counting per tracked object over a long horizon; the ranking column and
# minimap are navigation aids for keeping identities straight, never answers.

modalities_required:
  video: karts, ranking column and minimap are all visual.
  audio: not used.

question: For each race, count per kart how many powerup boxes it collected (the one quantity with no on-screen proxy).
output_schema: '{"races": [{"track": str, "karts": [{"kart": str, "items_collected": int}]}]}'  # other fields optional, unscored

ground_truth:
  source: SuperTuxKart 1.5 profile mode (--profile-laps) result table; the AI drives every
          kart and STK prints the exact per-kart telemetry, so the recorded run is its own
          ground truth. No replay-recorder keypress needed.
  tier: machine-truth
  verification: oracle solution.json = the profile table; judge.py scores it 1.0 through the
                harness path (solve.sh -> judge.py): 5 races, 10/10 karts matched, all tau = 1.0.

scorer:
  metric: "max(0, mean_races[tau(items)]); tau = SIGNED normalised Kendall correlation over
           kart pairs, aggregated across races then clamped once."
  oracle_reward: 1.0
  null_reward: 0.0
  measured_ablations:          # on the shipped ground truth, 500+ trials
    blind_guess: 0.035         # random counts, 600 trials (p95 0.149) on the 6x12 media
    constant_counts: 0.0       # every kart given the same count
    leaderboard_only: 0.0      # reads the ranking column/grid, reports no pickup info
    empty: 0.0
  measured_agents:            # Codex CLI v0.145.0, model gpt-5.6-sol, reasoning xhigh
    codex_6x12_items_only: re-running   # the shipped configuration
    codex_5x10_items_and_nitro: 0.170   # 24 turns, 581k tokens; nitro included (superseded)
    codex_5x10_items_only: 0.066        # same rollout, items-only rescore
    codex_4x6_items_only: 0.064         # 17 turns, 330k tokens; underpowered (60 pairs)
  # Calibration drove this design. Scoring finish + start too gave Codex 0.557 (tau 0.75 /
  # 0.90) because the ranking column and grid simply display them — leaderboard reading, not
  # understanding. Re-scoring that same rollout on the off-HUD pickup counts alone gave 0.064.
  # A second flaw was in the scorer itself: clamping tau per race discarded the negative half
  # of the noise, so random guessing averaged 0.156; signed tau aggregated then clamped once
  # puts the guess floor at 0.036.
  #
  # IMPORTANT, and the number that supersedes the others: on the SHIPPED 5x10 suite the same
  # harness scores 0.170, i.e. ABOVE the family's <0.10 bar. The earlier 0.064 was small-sample
  # noise (15 tau-pairs per field); with 45 pairs Codex's real partial ability shows, and 0.170
  # vs a 0.036 +- 0.052 floor is ~2.6 sigma above chance. Per-dimension mean tau: items ~0.07
  # (genuinely hard), nitro ~0.32 (easier — nitro use is visible as boost flames). Open design
  # question filed on the proposal issue: restrict to items, scale the field further, or accept
  # this as a medium-difficulty entry.

difficulty: {strong_agent_reward: TBD, tool_call_turns: TBD, agent_model: TBD}

anti_shortcut:
  single_frame: a single frame gives one instantaneous ranking, not the finishing order of
    four whole races, and no powerup totals.
  no_media: the four permutations and the pickup counts are not knowable blind — measured
    blind-guess floor 0.15.
  frame_dump_no_tools: TBD

input:
  url: https://huggingface.co/datasets/explcre/agenticvbench-understanding-materials/resolve/main/kart-race-telemetry-ledger-s1/race.mp4
  sha256: db77a2d39641e8111ffb32de478e891a45f9ac562e61dde1a92bc579715f3f77
  length_min: 41.5
  resolution: 720
  contents: 6 races (hacienda, snowmountain, lighthouse, cornfield_crossing, scotland,
            black_forest), 4 laps each, 12 karts each on SuperTux (hardest) AI difficulty;
            18 distinct characters. Twelve-kart fields are both harder to follow and
            statistically tighter: 66 tau-pairs per race x 6 = 396, against 225 at 5x10 and
            60 on the first 4x6 cut.
```

## Notes

- **Why it is a real reconstruction problem.** On SuperTux difficulty the AI takes good
  racing lines and uses nitro and powerups, so grid order is not finishing order — e.g. on
  cornfield_crossing the pole-sitter finished P3 and a grid-4 kart won. The outcome is only
  knowable by watching, and the ranking column plus the minimap are the evidence that lets a
  viewer follow karts that leave the chase camera.
- **Rank-agreement scoring is deliberate.** An exact-position + tolerant-count scheme was
  tried first and measured a blind-guess floor of 0.33 and a grid-only floor of 0.43 — a
  random permutation still lands 1-in-6 positions exactly, and sparse counts are almost
  always guessable. Kendall tau removes that free credit: guessing scores 0 in expectation
  because concordant and discordant pairs cancel. Partial knowledge still earns partial
  credit (podium-only ~0.56 in testing), which is the property that makes the task learnable
  rather than all-or-nothing.
- Ground-truth ties on item counts are excluded from tau's numerator and denominator, so the
  oracle is exactly 1.0 rather than being capped when two karts collect the same number.

## Fairness constraint enforced during generation

- **The field must be legible.** STK silently backfills an unknown kart id in `--aiNP` with a
  duplicate kart, which would put two identical-looking karts on track and make the ledger
  ambiguous. `parse_profile.py` asserts the parsed field size and rejects any duplicate, so
  every kart in the ground truth is a distinct visible character.

## Known limitations

- Powerup *counts* are harder to read precisely than finishing order; the 0.30 weight and the
  rank-only (not exact-count) scoring reflect that a viewer tracking twelve karts will order the
  pickups better than they will count them exactly. Measured per-dimension, nitro (~0.32) is
  easier for an agent than powerup boxes (~0.07), because nitro use shows as boost flames.
