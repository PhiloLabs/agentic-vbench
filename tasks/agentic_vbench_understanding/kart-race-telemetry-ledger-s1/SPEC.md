---
title: Task Spec Card
summary: kart-race-telemetry-ledger-s1 — reconstruct finishing order and per-kart powerup pickups across four AI-driven SuperTuxKart races.
---

# Task Spec Card

```yaml
task: agentic_vbench_understanding/kart-race-telemetry-ledger-s1

cognitive_level: understanding
# Follow six karts through each of four races on different tracks and reconstruct the
# outcome: the finishing order, and how many powerup boxes each kart collected. Multi-object
# tracking over a long horizon, using the on-screen ranking column and minimap as evidence.

modalities_required:
  video: karts, ranking column and minimap are all visual.
  audio: not used.

question: For each race, reconstruct per kart the powerup-box count and nitro count (off-HUD quantities).
output_schema: '{"races": [{"track": str, "karts": [{"kart": str, "start_position": int, "finish_position": int, "items_collected": int, "nitro_collected": int}]}]}'

ground_truth:
  source: SuperTuxKart 1.5 profile mode (--profile-laps) result table; the AI drives every
          kart and STK prints the exact per-kart telemetry, so the recorded run is its own
          ground truth. No replay-recorder keypress needed.
  tier: machine-truth
  verification: oracle solution.json = the profile table; judge.py scores it 1.0 through the
                harness path (solve.sh -> judge.py), all four races finish_tau = items_tau = 1.0.

scorer:
  metric: "max(0, mean_races[0.60*tau(items) + 0.40*tau(nitro)]); tau = SIGNED normalised
           Kendall correlation over kart pairs, aggregated then clamped once."
  oracle_reward: 1.0
  null_reward: 0.0
  measured_ablations:          # on the shipped ground truth, 500+ trials
    blind_guess: 0.036         # random counts, 600 trials (p95 0.146; was 0.057+-0.082 at 4x6)
    constant_counts: 0.0       # every kart given the same count
    leaderboard_only: 0.0      # reads the ranking column/grid, reports no pickup info
    empty: 0.0
  measured_agents:
    codex_gpt56: 0.064         # real run, 330k tokens, ~50 tool calls
  # Calibration drove this design. Scoring finish + start too gave Codex 0.557 (tau 0.75 /
  # 0.90) because the ranking column and grid simply display them — leaderboard reading, not
  # understanding. Scoring only the off-HUD pickup counts drops the same run to 0.064. A
  # second flaw was found in the scorer itself: clamping tau per race discarded the negative
  # half of the noise, so random guessing averaged 0.156; aggregating signed tau and clamping
  # once puts the guess floor at 0.06.

difficulty: {strong_agent_reward: TBD, tool_call_turns: TBD, agent_model: TBD}

anti_shortcut:
  single_frame: a single frame gives one instantaneous ranking, not the finishing order of
    four whole races, and no powerup totals.
  no_media: the four permutations and the pickup counts are not knowable blind — measured
    blind-guess floor 0.15.
  frame_dump_no_tools: TBD

input:
  url: https://huggingface.co/datasets/explcre/agenticvbench-understanding-materials/resolve/main/kart-race-telemetry-ledger-s1/race.mp4
  sha256: 3b22cf5b66301777fe69fb5d4435a4f8683da974084032d01b42fedd4141d75a
  length_min: 23.2
  resolution: 720
  contents: 5 races (hacienda, snowmountain, lighthouse, cornfield_crossing, scotland),
            4 laps each, 10 karts each on SuperTux (hardest) AI difficulty; 18 distinct
            characters. Ten-kart fields are both harder to follow and statistically tighter
            (45 tau-pairs per field instead of 15).
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
  rank-only (not exact-count) scoring reflect that a viewer tracking six karts will order the
  pickups better than they will count them exactly.
