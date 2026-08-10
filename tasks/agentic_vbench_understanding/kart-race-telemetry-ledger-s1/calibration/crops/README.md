# Observability: every scored action is visible on the hero (720p crops)

**The guarantee (by construction).** The camera is a chase-cam locked to the hero kart (`--kart=tux`)
for the entire race, and ONLY the hero's telemetry is scored. So every scored event — every powerup
box the hero drives through, every banana/bomb that hits it, and all of its drifting — happens
on-camera. No scored event can occur off-screen, so nothing caps the oracle below 1.0. (This is the
fix for the reviewer's twelve-kart observability point on #73.)

## Each scored quantity and its on-screen tell (3 scored: items, spinouts, skid_time)
1. **items_collected** — the hero drives THROUGH a floating question-mark / gift box on the track.
   The box is large and unmistakable at 720p (`zoom_item_box.png`, `spinout_and_itembox_720p.png`,
   and amid a start cluster in `pack_cluster_720p.png`). The HUD powerup slot is MASKED (black box,
   top-centre), so the pickup is counted from the visible drive-through, not read off a counter.
2. **spinouts** (= bananas + explosions, scored jointly) — a banana OR a bomb/cake hit spins the
   hero out with the same dizzy-stars tell (`hit_spinout_720p.png`, `zoom_spinout_stars.png`). Dense
   sampling of a 5-explosion race found NO visually-distinct explosion — banana and bomb are not
   reliably distinguishable at 720p — so only their sum (the visible spin-out event) is scored.
3. **skid_time** — drifting renders as a visible sideways slide with sparks off the wheels
   (`drift_720p.png`, `zoom_drift_sparks.png`). The *event* (drifting) is visible throughout;
   recovering the cumulative total seconds within tolerance is the hard part (and this dimension is
   not load-bearing — the task scores <0.10 even with skid_time removed).

## Contested pickups at 720p
`contested_startgrid_cluster_720p.png` / `pack_cluster_720p.png` — several karts clustered around the
hero at the start with item boxes still distinguishable, settling the review's "do contested pickups
resolve at 720p" point.

All frames are native 1280x720 from the shipped race.mp4.
