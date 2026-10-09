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
3. **skid_time** (visible-spark seconds) — drifting has a DISTINCT tell: bright **yellow sparks
   spray from BOTH rear wheels** while the kart skids through a turn (`drift_720p.png`,
   `zoom_drift_sparks.png`), and they are absent when it runs straight
   (`zoom_no_drift_straight.png` — the same kart on the same stretch of scotland 27 s later, no
   sparks). So "the sparks are on now" is witnessable, and their total duration is scorable (hard:
   time + sum them to within 30%). This is the drift skid-charge, distinct from the exhaust/nitro
   flame. The scored quantity is the SPARKS' duration, not "time spent drifting": after a long
   drift the spray continues through the 3-4 s skid bonus, which is why the prompt asks for the
   former (see SPEC.md, SKID DEFINITION AND TIMEBASE).

## Contested pickups at 720p
`contested_startgrid_cluster_720p.png` / `pack_cluster_720p.png` — karts clustered around the hero
at the start with item boxes still distinguishable (review point #73.2).

**Provenance.** All frames are native 1280x720, cut from the shipped `race.mp4`
(sha256 `1a75462b…`) at these video timestamps:

| file | video time | source race |
| --- | --- | --- |
| `drift_720p.png`, `zoom_drift_sparks.png` | 2718.00 s | scotland |
| `zoom_no_drift_straight.png` | 2745.00 s | scotland — the same kart 27 s later, sparks gone |
| `spinout_and_itembox_720p.png`, `zoom_spinout_stars.png` | 3819.00 s | stk_enterprise — dizzy-stars with item boxes in the same frame |
| `hit_spinout_720p.png` | 777.00 s | cornfield_crossing |
| `zoom_item_box.png` | 1360.00 s | gran_paradiso_island |
| `contested_startgrid_cluster_720p.png` | 12.00 s | hacienda |
| `pack_cluster_720p.png` | 2680.00 s | scotland |

Frames were located by ranking candidates on colour and then CHECKING EACH ONE BY EYE, because
colour alone cannot tell sparks from scenery: the first candidate set for the drift frames ranked
bright desert sand and a bomb explosion above every real drift. See generator/NOTES.md.

Every full-frame crop was checked to carry the mask rectangle that `generator/hud_mask.py` requires
(x 470..819, y 5..149, within the 3 px the lossy re-encode allows), so these frames show the same
HUD the agent sees. An earlier set was cut from a superseded render whose hand-fitted mask box was
x 512..767, y 0..131; that box matched neither the render it shipped with nor the derived one, which
is what `generator/verify_mask_box.py` now prevents.
