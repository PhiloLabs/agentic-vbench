---
title: Task Spec Card
summary: kart-race-telemetry-ledger-s1 — reconstruct the camera-followed hero kart's powerup pickups and drift-time across twelve AI-driven SuperTuxKart races, scored exactly against machine telemetry.
---

# Task Spec Card

```yaml
task: agentic_vbench_understanding/kart-race-telemetry-ledger-s1

cognitive_level: understanding
# The camera is a chase-cam locked to one hero kart (tux) for the whole suite. For each of twelve
# races the agent reconstructs TWO off-HUD quantities for the hero — how many powerup boxes it drove
# through, and how many seconds it spent drifting — neither shown as a number, and the powerup HUD
# slot is masked. Accurate fine-grained counting + a duration over a ~55-min horizon. The ranking
# column and minimap are navigation aids (position/timing), never answers.

modalities_required:
  video: the hero, the track boxes, the drift sparks, ranking column and minimap are all visual.
  audio: not used.

question: For each race, reconstruct the HERO kart's powerup boxes collected and drift seconds — both off-HUD — anchored to when the race happens in the video.
output_schema: '{"races": [{"track": str, "t": number, "items_collected": int, "skid_time": number}]}'  # t = video seconds; spinouts/bananas/nitro/positions optional, UNSCORED

ground_truth:
  source: SuperTuxKart 1.5 profile mode (--profile-laps) result table; the AI drives every kart and
          STK prints exact per-kart telemetry (bonus_count, banana_count, explosion_count, skid_time,
          ...). The camera follows the hero because the generator makes it the player kart (--kart=tux
          --ai=<rest>), so the recorded run is its own ground truth AND the scored kart is on screen
          the whole race. skid_time is RESCALED from telemetry game-seconds into VIDEO seconds (see
          SKID TIMEBASE below and generator/build_ground_truth.py).
  tier: machine-truth
  verification: oracle solution.json = the hero's telemetry rows; judge.py scores it 1.0 through the
                harness path (solve.sh -> judge.py) on both scored quantities.

scorer:
  metric: "EXACT + TIME-ANCHORED. Each predicted race is matched to the GT race whose video window
           [t_start,t_end] contains its reported time t (+/-15 s) — a count-vector at the wrong video
           segment earns nothing (not a bare rank permutation). Per quantity q: score_q =
           clamp(tau_q,0,1) * accuracy_q, where accuracy_q = mean over matched races of
           max(0, 1 - |pred-gt| / max(1, 0.30*gt)) and tau_q is the signed Kendall correlation (the
           guess gate). reward = COVERAGE * sum_q w_q*score_q, renormalised over quantities that vary
           in the GT, where coverage = matched_races / total_races: a GT race with no matched
           prediction (omitted, or timed into the wrong segment) contributes ZERO, so a partial answer
           cannot reach 1.0 (a correct 2-of-12 answer scores ~0.17) while the full oracle (all races
           matched) stays 1.0. Weights: items_collected 0.55, skid_time 0.45. Regression-tested in
           steps/solve/tests/test_coverage.py."
  # WHY exact, not rank. Rank agreement alone is too forgiving: an agent that systematically
  # UNDER-counts (Codex sees ~half the powerups) still ranks the races roughly right and scored ~0.35.
  # Scoring against STK's full-precision telemetry (within ~30% per race) removes that free credit.
  # The tau gate keeps it guess-proof: an ungated exact metric was rejected in an early design
  # (blind guessing 0.33), but multiplying by rank agreement drops blind guessing to ~0.02.
  # WHY only items + skid (spinouts dropped). n=3 calibration showed the dizzy-stars spin-out is
  # legible enough that a strong agent counts it well (accuracy up to 0.60), so scoring it broke the
  # <0.10 bar (2 of 3 Codex runs 0.10-0.19). The two quantities kept both genuinely defeat a strong
  # agent — it undercounts pickups ~half and cannot time drift to within 30%.
  oracle_reward: 1.0
  null_reward: 0.0
  measured_ablations:            # on the shipped 12-race ground truth, current 2-dim scorer
    correct_counts_wrong_times: 0.0    # right counts at shuffled video times -> the time window rejects
    blind_guess: 0.027           # random solutions (seed-dependent, ~0.007-0.03); the tau gate collapses guessing
    single_frame: 0.0            # one frame -> no per-race differentiation -> constant -> tau 0
    no_media: 0.009              # prompt + schema only; nothing to differentiate races
    ocr_only: 0.0                # NO scored quantity is on-screen text (HUD masked, off-HUD) -> guess
    constant_counts: 0.0         # every race identical -> predicted ties -> 0
    empty: 0.0

# SKID TIMEBASE (correctness). The software-GL capture runs BELOW realtime, and by a per-race factor
# (heavy tracks slow llvmpipe more), so a race of G game-seconds spans V > G video-seconds. Telemetry
# skid_time is in GAME seconds; the agent times drift off the VIDEO in VIDEO seconds. So the GT is
# rescaled per race: skid_time_video = skid_time_game * (video_clip_duration / game_race_duration).
# Measured per-race speed factors V/G (published so the map is auditable):
#   hacienda 1.13  snowmountain 1.31  cornfield_crossing 1.56  lighthouse 1.47  gran_paradiso 1.87
#   sandtrack 1.23  olivermath 1.18  cocoa_temple 1.75  scotland 1.28  fortmagma 1.31
#   ravenbridge 1.47  stk_enterprise 1.13   (mean 1.39). GT keeps skid_time_game + speed_factor per
# race for reference. Oracle = 1.0 on the rescaled values.

# OBSERVABILITY — both scored quantities are visible on the hero (crops in calibration/crops/):
#  * items_collected — the hero drives THROUGH a question-mark box (visible; HUD confirmation masked).
#  * skid_time (drift seconds) — drift has a DISTINCT tell: bright YELLOW sparks spray from BOTH rear
#    wheels while skidding (drift_720p.png / zoom_drift_sparks.png) and vanish the instant the kart
#    runs straight (zoom_no_drift_straight.png). Witnessable, and its duration scorable — HARD (time
#    + sum the drifts to within 30%). spinouts (banana/bomb dizzy-stars) is NOT scored: it is legible
#    enough to be countable by a strong agent, so it is not a difficulty lever; it stays as context.

difficulty: {strong_agent_reward: 0.0885, agent_model: gemini-3.5-flash}  # 2-dim; lineup max, still < 0.10
# MEETS the family's <0.10 strong-agent bar with margin. n=3 on the shipped video + shipped scorer:
#   Codex gpt-5.6-sol (xhigh): 0.030 / 0.000 / 0.052  (n=3, mean 0.027, max 0.052)
#   Claude Code (Opus 4.8):    0.045   (n=1)
#   Gemini CLI (gemini-3.5-flash): 0.0885 (n=1) — LINEUP MAX, still < 0.10; it counts powerups better
#     (items accuracy 0.31) so it is the tightest agent to the bar; skid still 0. (Gemini CLI, not the
#     Antigravity IDE, which cannot run headless here; model is the reviewer's named 3.5-flash.)
# Per-dim on the max Codex run: items accuracy ~0.01-0.05 (undercounts pickups ~half, almost never
# within 30%); skid accuracy ~0.13-0.17 (cannot time cumulative drift within 30% over a 55-min video).
# HISTORY of the hardening (all measured, Codex xhigh):
#   v2 hero-scope, rank agreement, 3 counts:              0.407
#   + HUD powerup mask (identification-hardness):         0.345
#   + EXACT-count metric (accuracy within 30%, not rank): items term 0.46 -> 0.10
#   + time-anchored (races matched by video time +/-15 s)
#   + skid_time rescaled to VIDEO seconds (timebase fix)
#   + DROP spinouts (too countable; broke the bar at n=3) -> items+skid, Codex n=3 mean 0.027
# FAIR + LEARNABLE: oracle = 1.0, blind-guess ~0.027; a within-30% agent scores far higher. Difficulty
# is ACCURATE pickup-counting under a masked HUD + a drift DURATION over a 55-min video, not a hack.

anti_shortcut:
  single_frame: 0.0     # one frame -> no per-race differentiation -> constant -> tau gate = 0
  no_media: 0.009       # prompt + schema only; the twelve races' quantities are not knowable blind
  ocr_only: 0.0         # neither scored quantity is on-screen text (HUD masked, off-HUD) -> guess
  frame_dump_no_tools:  # a 55-min video at 1 fps is >3000 frames, past any context window

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

- **Why it is a real reconstruction problem.** Neither scored quantity is displayed as a number.
  Recovering them means following the hero through every lap of every race and *accurately* measuring
  two independent things — powerup-box drive-throughs (HUD masked) and drift seconds — then reporting
  exact per-race values, not just an ordering. On SuperTux difficulty the hero genuinely fights for
  boxes and drifts hard corners.
- **Observability is the point.** The camera is locked to the hero and only the hero is scored, so
  every scored event is on screen by construction. `calibration/crops/` shows 720p frames of each
  scored tell (incl. the yellow drift sparks).
- **Exact scoring, guess-gated.** Accuracy (within ~30% of the machine value) forces real counting
  and timing; the tau gate zeroes a guesser. The oracle scores exactly 1.0.

## Fairness constraints enforced during generation

- **The hero is always present and always the camera target.** run_race.sh passes
  `--kart=<hero> --ai=<rest>`; build_ground_truth.py asserts the hero is in every race and that both
  scored fields vary, or it refuses to emit a degenerate ground truth.
- **The field stays legible.** parse_profile.py asserts the parsed field size and rejects duplicate
  kart ids (STK backfills unknown `--ai` ids with a duplicate), so every kart is a distinct visible
  character.

## Known limitations

- **skid_time timebase is corrected but approximate.** The GT rescales each race's drift-seconds from
  game-seconds to video-seconds by the per-race factor video_clip_duration / game_race_duration
  (published above). The factor is a whole-race average; if the software-GL slowdown is non-uniform
  *within* a race, the per-race drift total in video-seconds has some residual error — absorbed by the
  ±30% accuracy tolerance. The map was measured, not assumed (see build_ground_truth.py).
- **spinouts is not scored.** The dizzy-stars spin-out is legible enough that a strong agent counts it
  well (n=3: accuracy up to 0.60), so scoring it broke the <0.10 bar; it is kept as unscored context.
- Each race is TIME-ANCHORED: the GT tags every race with its video window and the agent must report
  each race's video time t, matched within +/-15 s (correct counts at the wrong segment score ~0 —
  see scorer, correct_counts_wrong_times 0.0). Per-EVENT ordering *within* a race (each pickup
  timestamped) would need machine-exact per-event times, which STK's prebuilt binary does not expose
  headless; per-race aggregates at per-race timestamps are the ceiling.
