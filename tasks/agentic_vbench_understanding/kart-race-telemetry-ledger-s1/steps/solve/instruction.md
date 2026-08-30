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
- **`skid_time`** — the **total seconds** (in video time) the hero spent **drifting** this race.
  Drifting has a distinct look: bright **yellow sparks spray from both rear wheels** while the kart
  skids through a turn (gone the instant it straightens out — not the same as the exhaust/boost
  flame). Add up how long, cumulatively, the hero was drifting. This is a *duration*, not a count.

Neither is displayed as a number anywhere. You may **optionally** also report `spinouts` (how many
times the hero spun out — it lurches and spins with dizzy stars overhead, from a banana or a bomb),
plus `nitro_collected`, `start_position` and `finish_position`, but **only `items_collected` and
`skid_time` are scored** — the ranking column and starting grid display the positions, and nitro
shows as a meter and boost flames.

## How it is scored

Your reported values are graded for **accuracy**: each `items_collected` and `skid_time` must be
within about **30%** of the true value for that race (a systematic under-count is penalised, not
forgiven — being roughly in the right order but consistently too low will not score well). Each race
you report is matched to the true race whose **video segment contains your `t`** (a **±15 s** window),
so anchor each race to the right point in the video — correct values placed at the wrong time earn
nothing. Only `items_collected` and `skid_time` are scored. Accurate counting of pickups and timing
of drift across the whole suite is the task.

Because only the hero is scored and the camera is on the hero the entire race, **every scored
event is on screen** — nothing you must measure happens off camera.

## What to submit

Write `/workspace/output/solution.json`, races in the order they appear in the video (the zeros
below show the SCHEMA only — replace them with your own observed values for each race):

```json
{
  "races": [
    {"track": "<first track shown>",  "t": 40,  "items_collected": 0, "spinouts": 0, "skid_time": 0},
    {"track": "<second track shown>", "t": 250, "items_collected": 0, "spinouts": 0, "skid_time": 0}
  ]
}
```

- `items_collected`: powerup boxes the **hero** drove through this race (a count). **Scored.**
- `skid_time`: total **seconds** the **hero** spent drifting (yellow wheel-sparks) this race (a duration). **Scored.**
- `t`: the video time in **seconds** (from the start) at which this race happens — any moment during
  the race, or its start. Your race is matched to the true race whose video segment contains this
  time (±15 s), so it need not be exact. **Required per race.**
- `spinouts`, `bananas_hit`, `times_exploded`, `track`, `nitro_collected`, `start_position`, `finish_position`: optional context, not scored.
- Races are matched to the ground truth by the video time `t` you give each — **not** by list order.

## Rules
- Stay inside this working directory. Do not read, write, or search outside it.
- Do not look anything up online. Reconstruct the results from the video.
- Report every race, in the order it appears.
