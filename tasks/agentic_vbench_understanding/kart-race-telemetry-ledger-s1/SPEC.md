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
# ~55-min horizon. The ranking column and minimap are navigation aids (position/timing), never answers.

modalities_required:
  video: the hero, the track boxes, the spin-outs, the drift sparks, ranking column and minimap are all visual.
  audio: not used.

question: For each race, reconstruct the HERO kart's powerup boxes collected, spin-outs (banana OR bomb, scored jointly), and drift seconds — all off-HUD — in race order.
output_schema: '{"races": [{"track": str, "t": number, "items_collected": int, "spinouts": int, "skid_time": number}]}'  # t = video seconds; bananas/nitro/positions optional, unscored

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
  metric: "EXACT + TIME-ANCHORED. Each predicted race is matched to the GT race whose video window
           [t_start,t_end] contains its reported time t (+/-15 s) — a count-vector at the wrong video
           segment earns nothing (not a bare rank permutation). Per quantity q: score_q =
           clamp(tau_q,0,1) * accuracy_q, where accuracy_q = mean over matched races of
           max(0, 1 - |pred-gt| / max(1, 0.30*gt)) and tau_q is the signed Kendall correlation (the
           guess gate). reward = sum_q w_q*score_q, renormalised over quantities that vary in the GT.
           Weights: items 0.40, spinouts 0.30, skid_time 0.30."
  # WHY exact, not rank. Rank agreement alone is too forgiving: an agent that systematically
  # UNDER-counts (Codex saw ~8 of 20 powerups) still ranks the races roughly right and scored ~0.35.
  # Scoring against STK's full-precision telemetry (within ~30% per race) removes that free credit.
  # The tau gate keeps it guess-proof: an ungated exact metric was rejected in an early design
  # (blind guessing 0.33), but multiplying by rank agreement drops blind guessing to ~0.02.
  oracle_reward: 1.0
  null_reward: 0.0
  measured_ablations:            # on the shipped 12-race ground truth
    correct_counts_wrong_times: 0.005  # right counts at shuffled video times -> the time window rejects
    blind_guess: 0.020           # random solutions; the tau gate collapses guessing
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

difficulty: {strong_agent_reward: 0.0892, agent_model: codex gpt-5.6-sol xhigh}  # shipped time-anchored 3-dim metric; n=1
# MEETS the family's <0.10 strong-agent bar. Per-dim on the shipped run (Codex matched all 12 races
# to the right video window):
#   items_collected: score 0.024 (tau 0.45, accuracy 0.05) — the agent undercounts powerups by ~half,
#                    so it is almost never within 30%; nearly unscored.
#   spinouts:        score 0.174 (tau 0.66, accuracy 0.26) — the dizzy-stars spin-out is the most
#                    legible event and carries most of the reward.
#   skid_time:       score 0.092 (tau 0.32, accuracy 0.29) — timing the cumulative drift to within
#                    30% over a 55-min video is hard.
# HISTORY of the hardening (all measured, Codex xhigh):
#   v2 hero-scope, rank agreement, 3 counts:              0.407
#   + HUD powerup mask (identification-hardness):         0.345 (items tau 0.64 -> 0.46)
#   + EXACT-count metric (accuracy within 30%, not rank): items term 0.46 -> 0.10
#   + merge banana+explosion -> spinouts (visually identical): positional re-score 0.0236
#   + TIME-ANCHORED (races matched by video time +/-15 s):     fresh run 0.0892
# n=1, run-dependent. The time window only ever REMOVES credit from a given submission (it adds a
# constraint), so it is strictly no easier; the 0.0892-vs-0.0236 gap is run-to-run variance (a fresh
# 12-race run that engaged more on spinouts vs a re-score of the earlier completed 542-call run), not
# the metric. Still FAIR + LEARNABLE: oracle = 1.0, blind-guess 0.020, correct-counts-wrong-times
# 0.005; a within-30% agent scores far higher. Difficulty is ACCURATE counting + a drift DURATION
# over a 55-min video, not a metric hack.

anti_shortcut:
  single_frame: one frame gives one instant, not twelve races of accurate per-kart counts + drift time.
  no_media: the twelve races' quantities are not knowable blind — measured blind-guess ~0.02.
  frame_dump_no_tools: a 55-min video at 1 fps is >3000 frames, past any context window, so an
    agent cannot ingest it without seeking tools.

input:
  url: https://huggingface.co/datasets/explcre/agenticvbench-understanding-materials/resolve/main/kart-race-telemetry-ledger-s1/race.mp4
  sha256: 4b4cee91675cf7b9699e645dc490343026a7022a2de008b7e1397c69ee59eb42
  length_min: 55.1
  resolution: 720
  contents: 12 races (hacienda, snowmountain, cornfield_crossing, lighthouse, gran_paradiso_island,
            sandtrack, olivermath, cocoa_temple, scotland, fortmagma, ravenbridge_mansion,
            stk_enterprise), 4 laps each, 10-kart fields on SuperTux (hardest) AI. The hero (tux) is
            in every race and the camera follows it throughout; the TOP-CENTER HUD powerup slot is
            MASKED (black box) so pickups must be caught from the hero driving through a box. The
            other nine karts race around it (contesting boxes, bombing it) for realism.

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
- Each race is now TIME-ANCHORED: the GT tags every race with its video window and the agent must
  report each race's video time t, matched within +/-15 s (correct counts at the wrong segment score
  ~0 — see scorer, ablation correct_counts_wrong_times 0.005). Per-EVENT ordering *within* a race
  (each pickup/spin-out timestamped) would need machine-exact per-event times, which STK's prebuilt
  binary does not expose headless; per-race aggregates at per-race timestamps are the ceiling.
