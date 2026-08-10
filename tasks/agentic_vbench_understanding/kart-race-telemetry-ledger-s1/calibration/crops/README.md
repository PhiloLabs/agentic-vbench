# 720p legibility crops — the four scored quantities are visible on the hero

Answering the review's "confirm contested pickups resolve at 720p when karts cluster; a few crops"
(issue #73, point 2), and demonstrating the four exact-scored off-HUD quantities are on-camera:

- `contested_startgrid_cluster_720p.png` — the start grid: several karts clustered around the hero
  with an item box (question-mark box) clearly distinguishable — a contested pickup resolves at 720p.
- `zoom_item_box.png` / `spinout_and_itembox_720p.png` — a powerup box (blue gift) is unmistakable
  even mid-race; **items_collected** = the hero driving through such boxes (HUD indicator is masked,
  so it is counted from the drive-through, not read off the HUD).
- `zoom_spinout_stars.png` — the dizzy-stars spin-out the hero shows when it hits a **banana**
  (`bananas_hit`) or is blown up (`times_exploded`); both are large, centred, unmistakable.
- `drift_720p.png` / `zoom_drift_sparks.png` — the spark streaks off the wheels while drifting;
  **skid_time** (total drift seconds) is estimated from these.

All frames are native 1280x720 from the shipped race.mp4. The HUD powerup slot is masked (black box,
top-centre) so pickups are not read off a counter.
