# Kart Race Telemetry Reconstruction

You are given one video at `/workspace/materials/race.mp4`: a suite of **five AI-driven
SuperTuxKart races**, one after another, each on a different track with **ten karts**. A race
change is obvious — the scene cuts to a new track and a new starting grid.

For each race, reconstruct **per kart: how many powerup boxes it collected** — the
question-mark boxes scattered around the track.

That number appears nowhere on screen, so you have to follow each kart through the race and
count. You may also report `nitro_collected`, `start_position` and `finish_position` for
context, but **only the powerup-box count is scored**: the ranking column and starting grid
display the positions, and nitro use shows as boost flames, so none of those require the
counting this task is measuring.

Evidence is on screen throughout:

- The **ranking column** (top left) lists the karts by current position, by character icon.
- The **minimap** (bottom left) shows every kart as a marker, so you can follow who is where
  even when a kart is off camera.
- Karts are visually distinct characters; the same character keeps its colours all race.
- A kart collects a powerup by driving through a **question-mark box**; the powerup then
  appears in that kart's slot.

## What to submit

Write `/workspace/output/solution.json`, races in the order they appear in the video:

```json
{
  "races": [
    {
      "track": "hacienda",
      "karts": [
        {"kart": "tux",    "start_position": 1, "finish_position": 2, "items_collected": 10, "nitro_collected": 12},
        {"kart": "amanda", "start_position": 4, "finish_position": 1, "items_collected": 17, "nitro_collected": 11}
      ]
    }
  ]
}
```

- `kart`: the character name as shown in game (for example `tux`, `gnu`, `konqi`, `nolok`,
  `amanda`, `beastie`, `kiki`, `adiumy`, `pidgin`, `puffy`, `hexley`, `wilber`, `xue`,
  `emule`, `gavroche`, `suzanne`, `sara_the_racer`, `sara_the_wizard`).
- `items_collected`: how many powerup boxes that kart drove through in that race. **Scored.**
- `nitro_collected`, `start_position`, `finish_position`, `track`: optional context, not scored.

## How it is scored

Scoring is **rank agreement** (normalised Kendall correlation), not exact match:

    reward = max(0, mean over races of agreement(items-collected order))

You do not have to count pickups exactly — ranking the karts by how many they collected is
what matters, so getting the heavy and light collectors in roughly the right order earns
credit. Guessing earns nothing: a random ordering scores 0 in expectation, because agreeing and
disagreeing pairs cancel out.

## Rules
- Stay inside this working directory. Do not read, write, or search outside it.
- Do not look anything up online. Reconstruct the results from the video.
- Report all five races, in the order they appear.
