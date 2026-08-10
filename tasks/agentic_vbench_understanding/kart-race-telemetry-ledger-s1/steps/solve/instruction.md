# Kart Race Telemetry Reconstruction

You are given one video at `/workspace/materials/race.mp4`: a suite of **AI-driven SuperTuxKart
races**, one after another, each on a different track. A race change is obvious — the scene cuts
to a new track and a new starting grid.

In every race the **camera follows one kart the whole time** — the same character (the *hero*)
in all races. It is the kart shown from behind, centred, with its name on the license plate; the
other karts race around it (competing for boxes, bombing it) but the camera stays on the hero.

For **each race**, reconstruct **four quantities for the hero kart**:
- **`items_collected`** — how many powerup boxes (the floating question-mark boxes on the track)
  the hero drove **through**. The HUD powerup indicator is **masked** (a black box covers the
  top-center slot), so there is no on-screen confirmation and no running total — you must catch
  each pickup from the hero visibly driving through a box.
- **`times_exploded`** — how many times the hero was blown up (hit by a bomb/cake: the kart is
  thrown into the air and spins out).
- **`bananas_hit`** — how many bananas the hero ran over (it visibly spins out, like a small
  slip); bananas are the yellow hazards dropped on the track, not the powerup boxes.
- **`skid_time`** — the **total seconds** the hero spent **drifting/skidding** in the race (the
  kart slides with sparks off the wheels while turning). This is a *duration*, not a count: add up
  how long, across the whole race, the hero was drifting.

None is displayed as a number anywhere. You may also report `nitro_collected`, `start_position`
and `finish_position` for context, but **only the four quantities above are scored** — the ranking
column and starting grid display the positions, and nitro shows as a meter and boost flames.

## How it is scored

Scoring is **exact**, not just rank — you are graded against SuperTuxKart's own telemetry:

    per quantity q:  score_q = clamp(rank_agreement_q, 0, 1) * accuracy_q
      accuracy_q = mean over races of  max(0, 1 - |your value - true| / max(1, 0.30*true))
    reward = max(0, 0.30*score_items + 0.15*score_explosions + 0.25*score_bananas + 0.30*score_skid)

Two things must both hold: your values must be **accurate** (within ~30% of the true value per
race — a systematic under-count is penalised, not forgiven), **and** they must rank the races
correctly (the rank term gates guessing — a constant or random answer scores ~0). Getting the
races in roughly the right order but with counts that are consistently too low will **not** score
well. Accurate counting/timing across a dozen races, on four independent quantities, is the task.

Because only the hero is scored and the camera is on the hero the entire race, **every scored
event is on screen** — nothing you must measure happens off camera.

## What to submit

Write `/workspace/output/solution.json`, races in the order they appear in the video:

```json
{
  "races": [
    {"track": "hacienda",     "items_collected": 24, "times_exploded": 1, "bananas_hit": 3, "skid_time": 69},
    {"track": "snowmountain",  "items_collected": 9, "times_exploded": 2, "bananas_hit": 0, "skid_time": 60}
  ]
}
```

- `items_collected`: powerup boxes the **hero** drove through this race. **Scored (weight 0.30).**
- `times_exploded`: how many times the **hero** was blown up this race. **Scored (weight 0.15).**
- `bananas_hit`: how many bananas the **hero** ran over this race. **Scored (weight 0.25).**
- `skid_time`: total **seconds** the **hero** spent drifting this race. **Scored (weight 0.30).**
- `track`, `nitro_collected`, `start_position`, `finish_position`: optional context, not scored.
- Report the races **in the order they appear** — they are matched to the ground truth by order.

## Rules
- Stay inside this working directory. Do not read, write, or search outside it.
- Do not look anything up online. Reconstruct the results from the video.
- Report every race, in the order it appears.
