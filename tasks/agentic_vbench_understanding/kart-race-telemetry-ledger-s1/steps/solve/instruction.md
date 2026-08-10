# Kart Race Telemetry Reconstruction

You are given one video at `/workspace/materials/race.mp4`: a suite of **AI-driven SuperTuxKart
races**, one after another, each on a different track. A race change is obvious — the scene cuts
to a new track and a new starting grid.

In every race the **camera follows one kart the whole time** — the same character (the *hero*)
in all races. It is the kart shown from behind, centred, with its name on the license plate; the
other karts race around it (competing for boxes, bombing it) but the camera stays on the hero.

For **each race**, reconstruct **two quantities for the hero kart**:
- **`items_collected`** — how many powerup boxes (the floating question-mark boxes on the track)
  the hero drove **through**. The HUD powerup indicator is **masked** (a black box covers the
  top-center slot), so there is no on-screen confirmation and no running total — you must catch
  each pickup from the hero visibly driving through a box.
- **`spinouts`** — how many times the hero **spun out** (it lurches and spins with dizzy stars
  overhead). A spin-out happens when the hero runs over a **banana** or is hit by a **bomb/cake**;
  both look the same on screen, so just count **every** spin-out — you do not need to tell the
  cause. (If you like, you may also report `bananas_hit` and `times_exploded` separately, but only
  their sum, `spinouts`, is scored.)

None is displayed as a number anywhere. You may also report `nitro_collected`, `start_position`
and `finish_position` for context, but **only the two quantities above are scored** — the ranking
column and starting grid display the positions, and nitro shows as a meter and boost flames.

## How it is scored

Scoring is **exact**, not just rank — you are graded against SuperTuxKart's own telemetry:

    per quantity q:  score_q = clamp(rank_agreement_q, 0, 1) * accuracy_q
      accuracy_q = mean over races of  max(0, 1 - |your value - true| / max(1, 0.30*true))
    reward = max(0, 0.55*score_items + 0.45*score_spinouts)

Two things must both hold: your values must be **accurate** (within ~30% of the true value per
race — a systematic under-count is penalised, not forgiven), **and** they must rank the races
correctly (the rank term gates guessing — a constant or random answer scores ~0). Getting the
races in roughly the right order but with counts that are consistently too low will **not** score
well. Accurate counting across a dozen races, on two independent quantities, is the task.

Because only the hero is scored and the camera is on the hero the entire race, **every scored
event is on screen** — nothing you must measure happens off camera.

## What to submit

Write `/workspace/output/solution.json`, races in the order they appear in the video (the zeros
below show the SCHEMA only — replace them with your own observed values for each race):

```json
{
  "races": [
    {"track": "<first track shown>",  "items_collected": 0, "spinouts": 0},
    {"track": "<second track shown>", "items_collected": 0, "spinouts": 0}
  ]
}
```

- `items_collected`: powerup boxes the **hero** drove through this race. **Scored (weight 0.55).**
- `spinouts`: how many times the **hero** spun out (banana or bomb) this race. **Scored (weight 0.45).**
- `bananas_hit`, `times_exploded`, `skid_time`, `track`, `nitro_collected`, `start_position`, `finish_position`: optional context, not scored.
- Report the races **in the order they appear** — they are matched to the ground truth by order.

## Rules
- Stay inside this working directory. Do not read, write, or search outside it.
- Do not look anything up online. Reconstruct the results from the video.
- Report every race, in the order it appears.
