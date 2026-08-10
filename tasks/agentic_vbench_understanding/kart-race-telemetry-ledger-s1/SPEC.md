---
title: Task Spec Card
summary: kart-race-telemetry-ledger-s1 — reconstruct the camera-followed hero kart's powerup pickups and spin-outs across twelve AI-driven SuperTuxKart races, scored exactly against machine telemetry.
---

# Task Spec Card

```yaml
task: agentic_vbench_understanding/kart-race-telemetry-ledger-s1

cognitive_level: understanding
# The camera is a chase-cam locked to one hero kart (tux) for the whole suite. For each of twelve
# races the agent reconstructs TWO off-HUD quantities for the hero — how many powerup boxes it drove
# through, and how many times it spun out — neither shown as a number, and the powerup HUD slot is
# masked. Accurate fine-grained counting over a ~53-min horizon. The ranking column and minimap are
# navigation aids (position/timing), never answers.

modalities_required:
  video: the hero, the track boxes, the spin-outs, ranking column and minimap are all visual.
  audio: not used.

question: For each race, reconstruct the HERO kart's powerup boxes collected and spin-outs (banana OR bomb, scored jointly as they look identical) — both off-HUD — in race order.
output_schema: '{"races": [{"track": str, "items_collected": int, "spinouts": int}]}'  # skid_time/bananas/explosions/nitro/positions optional, unscored

ground_truth:
  source: SuperTuxKart 1.5 profile mode (--profile-laps) result table; the AI drives every kart and
          STK prints exact per-kart telemetry (bonus_count, banana_count, explosion_count, ...). The
          camera follows the hero because the generator makes it the player kart (--kart=tux
          --ai=<rest>), so the recorded run is its own ground truth AND the scored kart is on screen
          the whole race.
  tier: machine-truth
  verification: oracle solution.json = the hero's telemetry rows; judge.py scores it 1.0 through the
                harness path (solve.sh -> judge.py) on both scored quantities.

scorer:
  metric: "EXACT, not just rank. Per quantity q: score_q = clamp(tau_q,0,1) * accuracy_q, where
           accuracy_q = mean over races of max(0, 1 - |pred-gt| / max(1, 0.30*gt)) and tau_q is the
           signed Kendall correlation over the races (the guess gate). reward = sum_q w_q*score_q,
           renormalised over quantities that vary in the GT. Weights: items 0.55, spinouts 0.45."
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

difficulty: {strong_agent_reward: 0.0201, tool_call_turns: 542, agent_model: codex gpt-5.6-sol xhigh}
# MEETS the family's <0.10 strong-agent bar. HISTORY of the hardening (all measured, Codex xhigh):
#   v2 hero-scope, rank agreement, 3 counts:            0.407
#   + HUD powerup mask (identification-hardness):       0.345 (items tau 0.64 -> 0.46)
#   + EXACT-count metric (accuracy within 30%, not rank): items term 0.46 -> 0.10
#   + observability fixes (see below): merge banana+explosion -> spinouts, drop skid_time:  0.0201
# Per-dim under the shipped 2-dim metric (Codex's 542-call run): items 0.015 (accuracy 0.04 —
# essentially NEVER within 30%, undercounts ~50%), spinouts 0.027. Requiring ACCURATE counts (not a
# forgiving ranking) over a 53-min video defeats Codex even with meticulous per-race vision. n=1; the
# 0.0201 re-scores the completed run under the final 2-dim metric — a fresh 2-dim-native run is being
# taken to confirm. Still FAIR + LEARNABLE: oracle = 1.0 and a within-30% agent scores far higher.
# What worked: the EXACT-count metric + identification-hardness (mask). Length was the weak lever
# (coverage is forgiving; a strong agent scales its sampling).

# OBSERVABILITY — every scored quantity is visible on the hero, and only cleanly-visible ones are scored:
#  * items_collected — the hero drives THROUGH a question-mark box (visible; HUD confirmation masked).
#  * spinouts (= banana_count + explosion_count) — the dizzy-stars spin-out. A banana hit and a bomb
#    hit render as the SAME spin-out and are NOT reliably distinguishable at 720p (dense sampling of a
#    5-explosion race found no consistently-distinct explosion), so only their SUM — the visible
#    spin-out event — is scored. The cause is not scored because it is not observable.
#  * DROPPED — skid_time (drift seconds): drifting cannot be cleanly separated from the near-constant
#    nitro-boost flames on screen, so drift duration is not reliably observable; scoring it would cap
#    the oracle below 1.0 unfairly. Retained in the GT as unscored context only. (It was not
#    load-bearing anyway — the task scores <0.10 on items+spinouts alone.)

anti_shortcut:
  single_frame: one frame gives one instant, not twelve races of accurate per-kart counts.
  no_media: the twelve races' counts are not knowable blind — measured blind-guess ~0.02.
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

- **Why it is a real reconstruction problem.** Neither scored quantity is displayed as a number.
  Recovering them means following the hero through every lap of every race and *accurately* counting
  two independent things — powerup-box drive-throughs (HUD masked) and spin-outs — then reporting
  exact per-race values, not just an ordering. On SuperTux difficulty the hero genuinely fights for
  boxes and is genuinely bombed/slipped, so the counts are non-trivial.
- **Observability is the point.** The camera is locked to the hero and only the hero is scored, so
  every scored event is on screen by construction. Quantities that are *not* cleanly visible
  (banana-vs-bomb cause; drift seconds vs nitro) are deliberately excluded from scoring — see the
  observability block above. `calibration/crops/` shows 720p frames of each scored tell.
- **Exact scoring, guess-gated.** Accuracy (within ~30% of the machine value) forces real counting;
  the tau gate zeroes a guesser. The oracle scores exactly 1.0.

## Fairness constraints enforced during generation

- **The hero is always present and always the camera target.** run_race.sh passes
  `--kart=<hero> --ai=<rest>`; build_ground_truth.py asserts the hero is in every race and that the
  primary scored field varies, or it refuses to emit a degenerate ground truth.
- **The field stays legible.** parse_profile.py asserts the parsed field size and rejects duplicate
  kart ids (STK backfills unknown `--ai` ids with a duplicate), so every kart is a distinct visible
  character.

## Known limitations

- Only two quantities are scored because they are the two that are cleanly observable on the hero at
  720p; banana-vs-explosion cause and drift-duration were investigated and excluded on observability
  grounds (see the scorer block). This keeps the task strictly fair (oracle reachable = 1.0) at the
  cost of breadth.
- A strictly harder ORDERED ledger (overtake / pickup sequence) would need machine-exact per-event
  order, which STK's prebuilt binary does not expose headless; per-race counts are the ceiling here.
