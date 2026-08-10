# Observability crops — the two scored actions are visible on the hero (720p)

**Guarantee (by construction).** The camera is locked to the hero (`--kart=tux`) all race and ONLY
the hero is scored, so every scored event is on-camera — nothing caps the oracle below 1.0.

## The two SCORED quantities and their on-screen tell
1. **items_collected** — the hero drives THROUGH a floating question-mark / gift box (large,
   unmistakable at 720p): `zoom_item_box.png`, `spinout_and_itembox_720p.png`, and amid a start
   cluster in `contested_startgrid_cluster_720p.png` / `pack_cluster_720p.png`. The HUD powerup slot
   is MASKED, so the pickup is counted from the visible drive-through, not read off a counter.
2. **spinouts** (= bananas + explosions) — the dizzy-stars spin-out: `hit_spinout_720p.png`,
   `zoom_spinout_stars.png`. A banana hit and a bomb hit produce the SAME spin-out and are NOT
   reliably distinguishable at 720p, so only their sum (the visible spin-out event) is scored.

## Why drift is NOT scored (observability)
`drift_720p.png` / `zoom_drift_sparks.png` are retained only to document why `skid_time` was
DROPPED: on screen the drift sparks are entangled with the near-constant nitro-boost flames, so
"is the hero drifting now" (let alone total drift seconds) is not reliably separable from boosting.
An unobservable quantity would cap the oracle unfairly, so drift is excluded from scoring (kept as
unscored context in the GT; it was not load-bearing — the task is <0.10 on items+spinouts alone).

## Contested pickups at 720p
`contested_startgrid_cluster_720p.png` / `pack_cluster_720p.png` — karts clustered around the hero
at the start with item boxes still distinguishable (review point #73.2).

All frames are native 1280x720 from the shipped race.mp4.
