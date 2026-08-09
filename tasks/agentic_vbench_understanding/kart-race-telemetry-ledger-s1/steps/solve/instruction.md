# Kart Race Telemetry Reconstruction

You are given one video at `/workspace/materials/race.mp4`: a suite of **AI-driven SuperTuxKart
races**, one after another, each on a different track. A race change is obvious — the scene cuts
to a new track and a new starting grid.

In every race the **camera follows one kart the whole time** — the same character (the *hero*)
in all races. It is the kart shown from behind, centred, with its name on the license plate; the
other karts race around it (competing for boxes, bombing it) but the camera stays on the hero.

For **each race**, reconstruct **two counts for the hero kart**:
- **`items_collected`** — how many powerup boxes (the question-mark boxes) the hero drove
  through. When it grabs one, the powerup appears in the hero's HUD slot (top of screen) — but
  there is never a running total, so you have to count the pickups as they happen.
- **`times_exploded`** — how many times the hero was blown up (hit by a bomb/cake: the kart is
  thrown into the air and spins out).

Both require watching the hero across the whole race and counting; neither is displayed as a
number anywhere. You may also report `nitro_collected`, `start_position` and `finish_position`
for context, but **only the two counts above are scored** — the ranking column and starting grid
display the positions, and nitro shows as a meter and boost flames, so none of those need the
counting this task measures.

## How it is scored

Scoring is **rank agreement across races** (normalised Kendall correlation), not exact match:

    reward = max(0, weighted mean over the two counts of
                    agreement( races ordered by the hero's count ))

You do not have to count exactly — ranking the **races** by how many powerups the hero collected
(and, separately, how many times it was blown up) is what earns credit, so getting the hero's
big-pickup and small-pickup races in roughly the right order scores well. Guessing earns nothing:
a random ordering scores 0 in expectation, because agreeing and disagreeing race-pairs cancel.

Because only the hero is scored and the camera is on the hero the entire race, **every scored
event is on screen** — nothing you must count happens off camera.

## What to submit

Write `/workspace/output/solution.json`, races in the order they appear in the video:

```json
{
  "races": [
    {"track": "hacienda",     "items_collected": 14, "times_exploded": 1},
    {"track": "snowmountain",  "items_collected": 2,  "times_exploded": 1}
  ]
}
```

- `items_collected`: powerup boxes the **hero** drove through this race. **Scored (weight 0.65).**
- `times_exploded`: how many times the **hero** was blown up this race. **Scored (weight 0.35).**
- `track`, `nitro_collected`, `start_position`, `finish_position`: optional context, not scored.
- Report the races **in the order they appear** — they are matched to the ground truth by order.

## Rules
- Stay inside this working directory. Do not read, write, or search outside it.
- Do not look anything up online. Reconstruct the results from the video.
- Report every race, in the order it appears.
