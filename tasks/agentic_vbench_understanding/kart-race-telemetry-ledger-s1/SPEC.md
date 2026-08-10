---
title: Task Spec Card
summary: kart-race-telemetry-ledger-s1 — reconstruct the camera-followed hero kart's powerup pickups, explosions, banana hits and drift-time across twelve AI-driven SuperTuxKart races, scored against exact machine telemetry.
---

# Task Spec Card

```yaml
task: agentic_vbench_understanding/kart-race-telemetry-ledger-s1

cognitive_level: understanding
# The camera is a chase-cam locked to one hero kart (tux) for the whole suite. For each of twelve
# races the agent reconstructs FOUR off-HUD quantities for the hero — powerup boxes driven through,
# times blown up, bananas hit, and total DRIFT SECONDS — none shown as a number, and the HUD
# powerup slot is masked. Fine-grained, accurate measurement (counts AND a duration) over a
# ~53-min horizon. The ranking column and minimap are navigation aids, never answers.

modalities_required:
  video: the hero, the track boxes/bananas, the drift sparks, ranking column and minimap are all visual.
  audio: not used.

question: For each race, reconstruct the HERO kart's powerup boxes collected, times exploded, bananas hit, and total drift seconds (all off-HUD), in race order.
output_schema: '{"races": [{"track": str, "items_collected": int, "times_exploded": int, "bananas_hit": int, "skid_time": number}]}'  # nitro/positions optional, unscored

ground_truth:
  source: SuperTuxKart 1.5 profile mode (--profile-laps) result table; the AI drives every kart and
          STK prints exact per-kart telemetry (bonus_count, explosion_count, banana_count,
          skid_time, ...). The camera follows the hero because the generator makes it the player
          kart (--kart=tux --ai=<rest>), so the recorded run is its own ground truth AND the scored
          kart is on screen the whole race.
  tier: machine-truth
  verification: oracle solution.json = the hero's telemetry rows; judge.py scores it 1.0 through the
                harness path (solve.sh -> judge.py) on all four quantities.

scorer:
  metric: "EXACT, not just rank. Per quantity q: score_q = clamp(tau_q,0,1) * accuracy_q, where
           accuracy_q = mean over races of max(0, 1 - |pred-gt| / max(1, 0.30*gt)) and tau_q is the
           signed Kendall correlation over the races (the guess gate). reward = sum_q w_q*score_q,
           renormalised over quantities that vary in the GT. Weights: items 0.30, explosions 0.15,
           bananas 0.25, skid_time 0.30."
  # WHY exact, not rank. The earlier scorer used rank agreement only, which is too forgiving: an
  # agent that systematically UNDER-counts (Codex saw 8 of 20 powerups) still ranks the races
  # roughly right and scored ~0.35. Scoring against STK's full-precision telemetry (within ~30% per
  # race) removes that free credit and is more faithful to the machine-exact GT. The tau gate keeps
  # it guess-proof: an ungated exact metric was rejected in the first design (blind guessing 0.33),
  # but multiplying by rank agreement drops blind guessing to ~0.02 (a guess has no rank to gate it).
  oracle_reward: 1.0
  null_reward: 0.0
  measured_ablations:            # on the shipped 12-race ground truth
    blind_guess: 0.019           # 300 random solutions; the tau gate collapses guessing
    constant_counts: 0.0         # every race identical -> predicted ties -> 0
    empty: 0.0
    codex_rescore_rank_vs_exact: "the earlier Codex rollout re-scored under this metric drops its
      items term 0.46 -> 0.096 (it under-counts); aggregate ~0.12 even before skid_time is asked for"

difficulty: {strong_agent_reward: ~0.12, tool_call_turns: >430, agent_model: codex gpt-5.6-sol xhigh}
# HISTORY of the hardening (all measured, Codex gpt-5.6-sol xhigh):
#   v2 hero-scope, rank, 3 counts:        0.407
#   + HUD powerup mask (identification):  0.345 (items tau 0.64 -> 0.46)
#   + EXACT-count metric + skid_time dim:  ~0.12  (see below)
# The exact-count number is the completed masked rollout RE-SCORED under this metric: 0.122 with
# skid_time unreported (->0), 0.174 if skid_time is excluded and the other three renormalised.
# Per-dim under exact-count: items 0.096, explosions 0.62 (sparse -> easy, hence its low 0.15
# weight), bananas 0.0 — the exact metric exposes that Codex systematically under-counts (it never
# gets within 30%). A FRESH full run reporting skid_time exceeded Codex's session budget (it did
# meticulous per-race vision analysis and reached only race 2/12 in ~100 min before dying) — itself
# a hardness signal, though it means the clean 4-quantity number is a re-score estimate (n=1).
# Levers that worked: identification-hardness (mask) and especially the EXACT-count metric (both
# attack WHAT the agent measures). Length was the weak lever (rank/coverage is forgiving). This is
# now a fair HARD entry, ~0.12 — near the family's <0.10 ideal, with items/bananas already ~0.05-0.10
# and only the deliberately-low-weight explosions holding the aggregate up.

anti_shortcut:
  single_frame: one frame gives one instant, not twelve races of accurate counts + drift durations.
  no_media: the twelve races' four quantities are not knowable blind — measured blind-guess 0.019.
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
            MASKED (black box) so pickups must be caught from the hero driving through a box. The
            other nine karts race around it (contesting boxes, bombing it) for realism.
```

## Notes

- **Why it is a real reconstruction problem.** None of the four quantities is displayed as a
  number. Recovering them means following the hero through every lap of every race and *accurately*
  measuring four independent things — three discrete-event counts (with the powerup HUD masked) and
  one cumulative duration (drift seconds) — then reporting exact values, not just an ordering. On
  SuperTux difficulty the hero is genuinely bombed, fights for boxes, and drifts hard corners.
- **Observability is the point.** Because the camera is locked to the hero and only the hero is
  scored, every scored quantity is on screen by construction — no off-camera event caps the score.
- **Exact scoring, guess-gated.** Accuracy (within ~30% of the machine value) forces real counting
  and timing; the tau gate zeroes a guesser. The oracle scores exactly 1.0.

## Fairness constraint enforced during generation

- **The hero is always present and always the camera target.** run_race.sh passes
  `--kart=<hero> --ai=<rest>`; build_ground_truth.py asserts the hero is in every race and that the
  primary scored field varies, or it refuses to emit a degenerate ground truth.
- **The field stays legible.** parse_profile.py asserts the parsed field size and rejects duplicate
  kart ids (STK backfills unknown `--ai` ids with a duplicate), so every kart is a distinct visible
  character.

## Known limitations

- `skid_time` is a *duration* — within ±30% is achievable for a careful viewer but hard, so it is
  a genuine difficulty lever; if calibration shows it is effectively unmeasurable it can be dropped.
- explosions are sparse (0-5) and easy to count exactly, so they carry the least weight (0.15).
- A strictly sub-0.10 kart would need a machine-exact ORDERED ledger (overtake/pickup sequence);
  STK's prebuilt binary exposes only per-race aggregates (no headless race-replay), so exact
  per-race telemetry is the ceiling for this engine.
