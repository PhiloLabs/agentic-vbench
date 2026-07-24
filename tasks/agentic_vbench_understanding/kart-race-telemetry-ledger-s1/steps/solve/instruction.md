# Kart Race Telemetry Reconstruction

You are given one video at `/workspace/materials/race.mp4`: a suite of **five AI-driven
SuperTuxKart races**, one after another, each on a different track with **ten karts**. A race
change is obvious — the scene cuts to a new track and a new starting grid.

For each race, reconstruct **per kart**:
- **how many powerup boxes it collected** (the question-mark boxes), and
- **how much nitro it picked up** (the small and large nitro cans along the track).

Neither number appears anywhere on screen — you have to follow each kart through the race and
count. You may also report `start_position` and `finish_position` for context, but they are
**not scored**: the ranking column and starting grid display them, so reading them off the HUD
is not what this task measures.

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
- `start_position`: grid slot, 1 for pole, up to 6.
- `finish_position`: 1 for the winner, up to 6.
- `items_collected`: how many powerup boxes that kart drove through in that race.
- `nitro_collected`: how many nitro cans that kart picked up.
- `track` is optional and not scored.

## How it is scored

Every field is scored as **rank agreement** (normalised Kendall correlation), not exact match:

    reward = max(0, mean over races of [ 0.60 * agreement(items order)
                                       + 0.40 * agreement(nitro order) ])

You do not have to count pickups exactly — ranking the karts by how many they collected is
what matters, so getting the heavy and light collectors in roughly the right order earns
credit. Guessing earns nothing: a random ordering scores 0 in expectation, because agreeing and
disagreeing pairs cancel out.

## Rules
- Stay inside this working directory. Do not read, write, or search outside it.
- Do not look anything up online. Reconstruct the results from the video.
- Report all five races, in the order they appear.
