---
title: Task Spec Card
summary: kart-race-telemetry-ledger-s1 — count the camera-followed hero kart's powerup pickups and explosions across eight AI-driven SuperTuxKart races, and rank the races by them.
---

# Task Spec Card

```yaml
task: agentic_vbench_understanding/kart-race-telemetry-ledger-s1

cognitive_level: understanding
# The camera is a chase-cam locked to one hero kart (tux) for the whole suite. For each of eight
# races the agent counts the hero's powerup-box pickups and the times it was blown up — neither is
# shown as a number, so it is fine-grained event counting over a long horizon, then a cross-race
# ranking. The ranking column and minimap are navigation aids, never answers.

modalities_required:
  video: the hero, its HUD powerup slot, the ranking column and minimap are all visual.
  audio: not used.

question: For each race, count the HERO kart's powerup boxes collected and times blown up (the two off-HUD quantities), reported in race order.
output_schema: '{"races": [{"track": str, "items_collected": int, "times_exploded": int}]}'  # track + nitro/positions optional, unscored

ground_truth:
  source: SuperTuxKart 1.5 profile mode (--profile-laps) result table; the AI drives every kart
          and STK prints the exact per-kart telemetry. The camera follows the hero because the
          generator makes it the player kart (--kart=tux --ai=<rest>), so the recorded run is its
          own ground truth AND the scored kart is on screen the whole race.
  tier: machine-truth
  verification: oracle solution.json = the hero's profile rows; judge.py scores it 1.0 through the
                harness path (solve.sh -> judge.py): 8 races, items tau 1.0 (27 pairs) and
                explosions tau 1.0 (23 pairs).

scorer:
  metric: "max(0, [0.65*tau(items) + 0.35*tau(explosions)] renormalised over the fields that vary
           in the GT); tau = SIGNED normalised Kendall correlation over the RACES, ordered by the
           hero's count. Renormalising lets the oracle reach 1.0 even if a field is flat."
  oracle_reward: 1.0
  null_reward: 0.0
  measured_ablations:          # on the shipped 8-race ground truth
    blind_guess: 0.086         # 600 random-count solutions; mean 0.086, p95 0.40 (small-N tail)
    constant_counts: 0.0       # every race given the same count -> all predicted ties -> 0
    empty: 0.0
    perfect_items_only: 0.513  # perfect items ranking + random explosions — the difficulty ceiling
  # HONEST DIFFICULTY NOTE. This task was rewritten to fix the observability flaw the reviewer
  # flagged on the issue: STK's profile camera is a chase-cam on ONE kart, so ranking all twelve
  # karts' pickups (the previous design) required counting eleven karts that are off camera —
  # unobservable, capping any real agent below the oracle's 1.0. Scoping the scored counts to the
  # single camera-followed hero makes every scored event visible ("scope the counts to what the
  # camera sees"), but it also makes the task easier: perfect items counting alone reaches ~0.51.
  # So this is now a FAIR, MEDIUM-difficulty entry, not a sub-0.10 one — the same honest standing
  # as the original submission (0.15). The difficulty knob is race count / laps: more races both
  # raise the counting load and shrink the blind-guess tail (8 races = 28 item-pairs; the guess
  # mean is already 0.086, but doubling the races roughly halves its p95).

difficulty: {strong_agent_reward: TBD (est. medium ~0.3-0.5), tool_call_turns: TBD, agent_model: TBD}
# Strong-agent calibration (Codex gpt-5.6-sol, README order) is pending a harness run; the estimate
# is bracketed by perfect-items (0.51) above and the recall-limited long-video behaviour seen on the
# sibling Minecraft task (agents watch only part of a long video) below.

anti_shortcut:
  single_frame: one frame gives one instantaneous ranking, not eight races' worth of pickup counts.
  no_media: the eight per-race counts are not knowable blind — measured blind-guess mean 0.086.
  frame_dump_no_tools: a 34-min video at 1 fps is >2000 frames, past any context window, so an
    agent cannot ingest it without seeking tools.

input:
  url: https://huggingface.co/datasets/explcre/agenticvbench-understanding-materials/resolve/main/kart-race-telemetry-ledger-s1/race.mp4
  sha256: 27c56bfcad6d5d9cf8253b2f7fc48bb781d8dce3aa38ac0bc2d4c13f7959ea05
  length_min: 34.5
  resolution: 720
  contents: 8 races (hacienda, snowmountain, cornfield_crossing, lighthouse, gran_paradiso_island,
            sandtrack, black_forest, cocoa_temple), 3 laps each, 10-kart fields on SuperTux
            (hardest) AI. The hero (tux) is in every race and the camera follows it throughout;
            the other nine karts race around it (contesting boxes, bombing it) for realism.
```

## Notes

- **Why it is a real reconstruction problem.** The hero's pickups and explosions are shown nowhere
  as a number; recovering them means following the hero through every lap of every race and
  counting discrete events, then ordering the eight races by those tallies. On SuperTux difficulty
  the hero is genuinely bombed and genuinely fights for boxes, so the counts are non-trivial.
- **Observability is the point.** Because the camera is locked to the hero and only the hero is
  scored, every scored event is on screen by construction — there is no off-camera pickup that
  caps the achievable score, which was the flaw in the twelve-kart version.
- **Rank-agreement scoring is deliberate.** Kendall tau over the races keeps the guessing floor
  near 0 (concordant and discordant race-pairs cancel) while granting partial credit for a partial
  ordering. Ground-truth ties are excluded from tau's numerator and denominator so the oracle is
  exactly 1.0.

## Fairness constraint enforced during generation

- **The hero is always present and always the camera target.** run_race.sh passes
  `--kart=<hero> --ai=<rest>`; build_ground_truth.py asserts the hero appears in every race's
  parsed field and that the primary scored field (items) varies across races, or it refuses to
  emit a degenerate ground truth.
- **The field stays legible.** parse_profile.py asserts the parsed field size and rejects
  duplicate kart ids (STK silently backfills an unknown `--ai` id with a duplicate), so every kart
  on track is a distinct visible character.

## Known limitations

- Scoping to the hero fixed fairness at the cost of difficulty (see the difficulty note above); the
  task is now medium, and race count / laps are the knobs to harden it if calibration warrants.
- Explosions are sparser than items (0–4 per race); the judge renormalises so a flat explosion
  column would not cap the oracle, but on the shipped suite both fields vary and both are scored.
