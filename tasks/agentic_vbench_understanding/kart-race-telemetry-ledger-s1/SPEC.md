---
title: Task Spec Card
summary: kart-race-telemetry-ledger-s1 — reconstruct the camera-followed hero kart's powerup pickups, spin-outs and drift-time across twelve AI-driven SuperTuxKart races, scored exactly against machine telemetry.
---

# Task Spec Card

```yaml
task: agentic_vbench_understanding/kart-race-telemetry-ledger-s1

cognitive_level: understanding
# The camera is a chase-cam locked to one hero kart (tux) for the whole suite. For each of twelve
# races the agent reconstructs THREE off-HUD quantities for the hero — how many powerup boxes it
# drove through, how many times it spun out, and how many seconds it spent drifting — none shown as
# a number, and the powerup HUD slot is masked. Accurate fine-grained counting + one duration over a
# ~53-min horizon. The ranking column and minimap are navigation aids (position/timing), never answers.

modalities_required:
  video: the hero, the track boxes, the spin-outs, the drift sparks, ranking column and minimap are all visual.
  audio: not used.

question: For each race, reconstruct the HERO kart's powerup boxes collected, spin-outs (banana OR bomb, scored jointly), and drift seconds — all off-HUD — in race order.
output_schema: '{"races": [{"track": str, "items_collected": int, "spinouts": int, "skid_time": number}]}'  # bananas/explosions/nitro/positions optional, unscored

ground_truth:
  source: SuperTuxKart 1.5 profile mode (--profile-laps) result table; the AI drives every kart and
          STK prints exact per-kart telemetry (bonus_count, banana_count, explosion_count, skid_time,
          ...). The camera follows the hero because the generator makes it the player kart (--kart=tux
          --ai=<rest>), so the recorded run is its own ground truth AND the scored kart is on screen
          the whole race.
  tier: machine-truth
  verification: oracle solution.json = the hero's telemetry rows; judge.py scores it 1.0 through the
                harness path (solve.sh -> judge.py) on all three scored quantities.

scorer:
  metric: "EXACT, not just rank. Per quantity q: score_q = clamp(tau_q,0,1) * accuracy_q, where
           accuracy_q = mean over races of max(0, 1 - |pred-gt| / max(1, 0.30*gt)) and tau_q is the
           signed Kendall correlation over the races (the guess gate). reward = sum_q w_q*score_q,
           renormalised over quantities that vary in the GT. Weights: items 0.40, spinouts 0.30, skid_time 0.30."
  # WHY exact, not rank. Rank agreement alone is too forgiving: an agent that systematically
  # UNDER-counts (Codex saw ~8 of 20 powerups) still ranks the races roughly right and scored ~0.35.
  # Scoring against STK's full-precision telemetry (within ~30% per race) removes that free credit.
  # The tau gate keeps it guess-proof: an ungated exact metric was rejected in an early design
  # (blind guessing 0.33), but multiplying by rank agreement drops blind guessing to ~0.02.
  oracle_reward: 1.0
  null_reward: 0.0
  measured_ablations:            # on the shipped 12-race ground truth
    blind_guess: 0.020           # 300 random solutions; the tau gate collapses guessing
    constant_counts: 0.0         # every race identical -> predicted ties -> 0
    empty: 0.0

# OBSERVABILITY — every scored quantity is visible on the hero; only cleanly-visible ones are scored
# (crops in calibration/crops/):
#  * items_collected — the hero drives THROUGH a question-mark box (visible; HUD confirmation masked).
#  * spinouts (= banana_count + explosion_count) — the dizzy-stars spin-out. A banana hit and a bomb
#    hit render as the SAME spin-out and are NOT reliably distinguishable at 720p, so only their SUM
#    (the visible spin-out event) is scored — the cause is not scored because it is not observable.
#  * skid_time (drift seconds) — drift has a DISTINCT tell: bright YELLOW sparks spray from BOTH rear
#    wheels while skidding (drift_720p.png / zoom_drift_sparks.png) and vanish the instant the kart
#    runs straight (zoom_no_drift_straight.png). So drift is witnessable and its duration is scorable
#    — HARD (time + sum the drifts to within 30%) but fair. It is not load-bearing: items+spinouts
#    alone already score <0.10.

difficulty: {strong_agent_reward: 0.0236, tool_call_turns: 542, agent_model: codex gpt-5.6-sol xhigh}
# MEETS the family's <0.10 strong-agent bar. HISTORY of the hardening (all measured, Codex xhigh):
#   v2 hero-scope, rank agreement, 3 counts:              0.407
#   + HUD powerup mask (identification-hardness):         0.345 (items tau 0.64 -> 0.46)
#   + EXACT-count metric (accuracy within 30%, not rank): items term 0.46 -> 0.10
#   + observability fix: merge banana+explosion -> spinouts (they are visually identical): 0.0236
# Per-dim (Codex's completed 542-call run, re-scored under the shipped 3-dim metric): items 0.015
# (accuracy 0.04 — essentially NEVER within 30%, undercounts ~50%), spinouts 0.027, skid_time 0.032.
# Requiring ACCURATE counts + a drift DURATION over a 53-min video defeats Codex even with meticulous
# per-race vision. n=1; 0.0236 re-scores the completed run under the final 3-dim metric. Still FAIR +
# LEARNABLE: oracle = 1.0 and a within-30% agent scores far higher. What worked: the EXACT-count
# metric + identification-hardness (mask). Length was the weak lever (coverage is forgiving; a strong
# agent scales its sampling — confirmed on the sibling MC task: 628ev->1046ev only moved 0.355->0.236).

anti_shortcut:
  single_frame: one frame gives one instant, not twelve races of accurate per-kart counts + drift time.
  no_media: the twelve races' quantities are not knowable blind — measured blind-guess ~0.02.
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
  annotated_explainer: kart-race-telemetry-ledger-s1/race_annotated_explainer.mp4  # same footage with
            per-race captions naming the scored quantities; a human aid, NOT the task input.

```

## Notes

- **Why it is a real reconstruction problem.** None of the three scored quantities is displayed as a
  number. Recovering them means following the hero through every lap of every race and *accurately*
  measuring three independent things — powerup-box drive-throughs (HUD masked), spin-outs, and drift
  seconds — then reporting exact per-race values, not just an ordering. On SuperTux difficulty the
  hero genuinely fights for boxes, is genuinely bombed/slipped, and drifts hard corners.
- **Observability is the point.** The camera is locked to the hero and only the hero is scored, so
  every scored event is on screen by construction. A quantity that is *not* cleanly visible (the
  banana-vs-bomb cause) is deliberately excluded from scoring — see the observability block.
  `calibration/crops/` shows 720p frames of each scored tell (incl. the yellow drift sparks).
- **Exact scoring, guess-gated.** Accuracy (within ~30% of the machine value) forces real counting
  and timing; the tau gate zeroes a guesser. The oracle scores exactly 1.0.

## Fairness constraints enforced during generation

- **The hero is always present and always the camera target.** run_race.sh passes
  `--kart=<hero> --ai=<rest>`; build_ground_truth.py asserts the hero is in every race and that the
  primary scored field varies, or it refuses to emit a degenerate ground truth.
- **The field stays legible.** parse_profile.py asserts the parsed field size and rejects duplicate
  kart ids (STK backfills unknown `--ai` ids with a duplicate), so every kart is a distinct visible
  character.

## Known limitations

- Only banana-vs-explosion CAUSE is excluded from scoring (unobservable — both are the same
  spin-out); the three scored quantities are each cleanly observable on the hero at 720p.
- `skid_time` (drift seconds) is the hardest dimension: the drift event is clearly visible (yellow
  wheel sparks) but summing the total duration to within 30% is demanding. It is not load-bearing —
  the task scores <0.10 on items+spinouts alone — so it adds difficulty without gating fairness.
- A strictly harder ORDERED ledger (overtake / pickup sequence) would need machine-exact per-event
  order, which STK's prebuilt binary does not expose headless; per-race aggregates are the ceiling.
