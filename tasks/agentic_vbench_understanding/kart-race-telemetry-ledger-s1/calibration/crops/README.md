# Observability crops — the scored quantities are visible on the hero (720p)

**Guarantee (by construction).** The camera is locked to the hero (`--kart=tux`) all race and ONLY
the hero is scored, so every scored event is on-camera — nothing caps the oracle below 1.0.

## The SCORED quantities (items_collected, skid_time) + the observable-but-unscored spinout
1. **items_collected** — the hero drives THROUGH a floating question-mark / gift box (large,
   unmistakable at 720p): `zoom_item_box.png`, `spinout_and_itembox_720p.png`, and amid a start
   cluster in `contested_startgrid_cluster_720p.png` / `pack_cluster_720p.png`. The HUD powerup slot
   is MASKED, so the pickup is counted from the visible drive-through, not read off a counter.
2. **spinouts** (= bananas + explosions) — UNSCORED context (observable but too countable to score) — the dizzy-stars spin-out: `hit_spinout_720p.png`,
   `zoom_spinout_stars.png`. A banana hit and a bomb hit produce the SAME spin-out and are NOT
   reliably distinguishable at 720p; the spin-out is UNSCORED context (it is too countable to be a
   difficulty lever), so only its visible occurrence is described here, not scored.
3. **skid_time** (drift seconds) — drifting has a DISTINCT tell: bright **yellow sparks spray from
   BOTH rear wheels** while the kart skids through a turn (`drift_720p.png`, `zoom_drift_sparks.png`),
   and they VANISH the instant the kart runs straight (`zoom_no_drift_straight.png` — same kart,
   seconds later, no sparks). So "the hero is drifting now" is witnessable, and total drift seconds
   is scorable (hard: time + sum the drift episodes to within 30%). This is the drift skid-charge,
   distinct from the exhaust/nitro flame.

## Contested pickups at 720p
`contested_startgrid_cluster_720p.png` / `pack_cluster_720p.png` — karts clustered around the hero
at the start with item boxes still distinguishable (review point #73.2).

**Provenance — REGENERATION REQUIRED before merge (measured 2026-09-04).** These frames are native
1280x720, but they are NOT from the current render. Measured on the five full-frame crops, the
blacked-out HUD rectangle in them is x 512..767, y 0..131. The render that shipped before this fix
used x 505..814, y 5..144, and the rectangle the geometry actually requires (generator/hud_mask.py)
is x 470..819, y 5..149. So the mask box drifted across three renders while it was hand-fitted,
which is what the derivation plus generator/verify_mask_box.py now prevents. The crops still show
what they are cited for -- the item box, the dizzy-stars spin-out, and the yellow drift sparks are
rendered identically -- but any frame here that includes the top-centre HUD misrepresents the
shipped mask, so these need re-cutting from the current race.mp4 (they are reviewer evidence only;
no agent-facing file references them).
