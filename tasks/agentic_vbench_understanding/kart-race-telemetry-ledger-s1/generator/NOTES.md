# P4 — SuperTuxKart race-telemetry ledger: build notes

## Ground truth is solved (2026-07-22)

The blocker was triggering STK's replay recorder without a keypress. It is unnecessary:
**profile mode** drives every kart by AI and prints a machine-exact per-kart table to stdout.

```sh
cd SuperTuxKart-1.5-linux-x86_64
./run_game.sh --no-graphics --profile-laps=2 --track=hacienda --numkarts=6 \
              --aiNP=tux,gnu,adiumy,amanda,beastie,kiki
```

Printed columns (one row per kart, in grid order):

```
name start_position end_position time average_speed top_speed skid_time rescue_time
rescue_count brake_count explosion_time explosion_count bonus_count banana_count
small_nitro_count large_nitro_count bubblegum_count
```

Notes learned the hard way:
- Short flags `-t` / `-k` are rejected in this build — use `--track=` / `--numkarts=`.
- `--aiNP=` = AI karts with **no** player kart, so nothing needs input. Unknown kart names
  are silently dropped (`sara` is not a kart id; `sara_the_racer` is), which silently
  changes the field size — always assert the row count equals `--numkarts`.
- Headless runs at ~11 000 FPS: a 2-lap 6-kart race profiles in under a second, so GT is
  cheap to regenerate.
- Profile mode works with graphics on as well, so the *recorded* run can be its own GT —
  no cross-run determinism assumption needed.

## The HUD mask is verified by its box, not by hunting sprites (2026-09-04)

The first mask box was hand-fitted from a comment that mis-stated the sprite geometry, and it was
35 px too narrow on the left. `hud_mask.py` now derives the rectangle from STK's own drawing code
and self-tests it: at 1280x720 a single local player gives scale 1.6, so icons are 102 px tall at
y 32..134, and because the row is centred it is widest at `MAX_POWERUPS = 5`, spanning x 488..794.
The old box started at x=505, so with five items held a 17 px strip of the leftmost icon stayed
visible — enough to signal both that an item was held and, from the shifted layout, how many.

The obvious check — look for the sprites in the rendered video — does not work, and this was
measured rather than assumed. A held sprite is static while the scenery moves, so a burst of
consecutive frames separates it in principle; in practice STK powerup icons are mostly transparent
(`icon-bubblegum.png` is 22% opaque, mean alpha 0.28), so only a sprite's opaque core is static,
and the surviving signal does not separate from ordinary scenery. Sweeping the static-row and
texture thresholds over 40 scenery bursts plus a held-out set of 40: every setting sensitive enough
to catch a 17 px sliver also fired on 3–6 scenery bursts, and every setting that silenced scenery
also missed the sliver. Detecting the black box instead is unambiguous — it is found in 24/24
sampled frames, to the pixel — so `verify_mask_box.py` measures the shipped rectangle and compares
it to the derived one, and is checked in both directions (it must report the unmasked concat as
unmasked). Frames that are black all over, the transitions between races, are why presence needs
an agreement threshold rather than a single hit.

## Rendering path

Xvfb + `LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe` (swrast present on this node),
captured with ffmpeg `x11grab` (module ffmpeg/4.2.2 has it). Software GL runs well below
realtime, so wall-clock capture yields a long slow-motion video — which suits a 10 min+
task and makes kart identity easier to track, but the HUD must be cropped out.

## Task shape

Question: for the camera-followed **hero kart**, per race, reconstruct the two off-HUD scored
quantities `{items_collected, skid_time}` (spinouts = bananas + explosions, reported but UNSCORED; positions /
nitro / the banana-vs-bomb split are exported for context but not scored — see the task SPEC).
Deterministic scorer: exact-count (`clamp(tau,0,1) · within-30%-accuracy`) over the 12 races, so a
single-frame glance cannot recover it and accurate counting/timing requires watching each race.
