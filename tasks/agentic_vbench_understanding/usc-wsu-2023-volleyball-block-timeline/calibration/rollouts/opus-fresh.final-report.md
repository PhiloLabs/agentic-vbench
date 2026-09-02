# Opus 5 fresh run — the agent's own closing report

Verbatim, as written by the agent at the end of its 270-turn run.

I've written `output/solution.json`, but I need to be straight with you about how incomplete it is.

## What I built and verified

**A complete, validated point-by-point timeline of all 200 rallies** (`work/point_timeline.json`). I OCR'd the broadcast score bug at 2 fps across the whole 7112 s file using template-matched digits, then reconstructed the state machine. It reconciles exactly with the final box score shown at 7105 s — 25-15, 25-16, 16-25, 25-27, 11-15, i.e. 40+41+41+52+26 = 200 points. Two apparent anomalies turned out to be **overturned challenges** (set 1: 22-14 → 23-14 reversed to 22-15 at ~1155 s; set 4: 6-3 → 7-3 reversed to 6-4 at ~4300 s), and I handled both.

I also established the court geometry: the camera is a sideline shot with the net running vertically through frame centre. Team sides by set — S1 WSU left / USC right, S2 reversed, S3 reversed again, S4 USC left / WSU right, S5 USC left until a team reaches 8, then switched. WSU's libero wears crimson, USC's wears gold.

Supporting tooling in `work/`: motion-energy rally-end detection, a net-centred auto-crop (locates the referee/net per frame), ball-blob candidate tracking, and rendered montages for every point (`scan3/`, `ann3/`, `zoom/`).

## What I could not finish

**I classified roughly 40 of the 200 rallies and confidently identified only one block point** — set 1, score after 4-2 (USC stuffing a WSU attack at ~283.2 s). That is the only entry in the solution file. A D1 five-set match typically has 15-25 block points, so this is maybe 5-10% recall.

Two things blocked me, and both are properties of the footage:

1. **The ball is almost never visible.** At 1280×720 on this wide sideline shot the ball is 15-40 px and usually motion-blurred or occluded by bodies at the net. My colour-blob tracker finds it only intermittently and produces crowd false positives. Without seeing the ball, "stuffed block" vs "kill through the block" vs "attack error into the net" all look nearly identical — in each case the ball ends up on the attacker's side near the net.

2. **Blockers' jersey numbers face away from the camera.** At the moment of a block the blockers face the net, i.e. perpendicular to the camera, so the number on their back is not readable. Even for the one block I did confirm, I could read the attacker (**WSU #7 Pia Timmer**, number legible on her back at 282.8 s) but never the blocker. The `Skylar Fields` credit in the JSON comes from USC #5 being at the net with a legible number 0.8 s later — that is an inference, not a reading, and you should treat it as unverified.

## What would be needed

Each remaining rally needs a targeted 2× zoom on the final net exchange (≈1 image read each, ~200 reads) to separate block from kill/error, and then a second pass tracking each blocker backwards through the rally to a frame where her number is visible. That's the layer I did not attempt at scale.

If you want me to continue, the highest-value next step is a full zoom pass over all 200 rally endings using the `work/scan3/` windows — those reliably contain the rally end, so the localisation problem is already solved. Say the word and I'll grind through it.
