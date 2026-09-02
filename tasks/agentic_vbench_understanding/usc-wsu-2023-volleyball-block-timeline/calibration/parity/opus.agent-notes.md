# USC @ Washington State — block-timeline task: state of work

## Delivered
`output/solution.json` — currently `{"events": []}`. This is **not** a claim that the
match contained no block points; it records that I could not verify any individual
rally as a block to the standard the task requires. See "Where it broke down".

## Verified intermediate result: full point-by-point score timeline
Reconstructed from the broadcast score bug and cross-checked against the video.

Pipeline (scripts in `scripts/`, run inside the task container):
1. `seg_gray.py` — 12 parallel segments, `-ss S -copyts -t 610 -vf fps=2,crop=340:66:470:584`,
   grayscale, with per-frame `showinfo` PTS captured so every sample is time-pinned.
2. `gplateaus.py` — frames where the bug is up (mean of the SET SCORE plate in 171..178);
   split into plateaus on frame-to-frame MAD > 8 over the two score boxes.
3. `cluster_runs.py` + manual labelling of ~35 cluster representatives per side.
4. `points.py` — 196 point transitions, validated against volleyball's own constraint
   (each transition must be +1 to exactly one side).

Result — 196 of the match's 200 points recovered; the 4 missing are set-enders that the
broadcast never displayed (the graphic cuts to the set-summary card):

| set | detected | first→last shown | actual final |
|-----|----------|------------------|--------------|
| 1 | 40 | 1-0 → 24-15 | 25-15 USC |
| 2 | 40 | 0-1 → 24-16 | 25-16 USC |
| 3 | 39 | 0-2 → 16-24 | 16-25 WSU |
| 4 | 52 | 1-0 → 25-26 | 25-27 WSU |
| 5 | 25 | 0-1 → 11-14 | 11-15 WSU |

Match: USC 2, Washington State 3.

Two score corrections (overturned calls) are visible and were handled, not treated as
OCR error: set 1 at ~t=1180 (23-14 → 22-15) and set 4 at ~t=4408 (7-3 → 6-4).

Artifacts: `data/points.json`, `data/states2.json`, `data/pt_rally.json`,
`data/liveruns.json`, `data/seg/`.

## Rally-end anchoring
The score graphic lags the whistle by a variable 1.5–6 s, so the graphic time alone is
not a usable anchor. Live-play frames were separated from cut-ins by a two-band
brightness test on 4 fps 128x72 frames (`mean(rows 26..48) - mean(rows 0..16) > 60`),
which separates cleanly (live ≈ 90–110, cut-ins ≈ −27..24). 265 live runs; all 196
points anchored, 168 of them by a camera cut within ~0.5–3.5 s of the ball landing.

## Where it broke down
Deciding *how* each rally ended needs the ball, and the ball is the problem:
- Live play is shot from a high side camera; the ball is ~8–14 px and often motion-blurred.
- At 0.3–0.45 s sampling — the density at which a whole point fits in one readable
  contact sheet — the ball is usually not visible at all.
- At 0.1 s sampling the ball *is* readable (verified on points #4 and #19), but each such
  sheet covers only ~1.2 s, so it needs an anchor tighter than the ±3.5 s I can derive,
  and it is one image per point on top of the screening image.
- The broadcast shows **no replays**, so there is no second look at any rally.
- A colour-based ball detector (the ball is bluish-white, the floor tan) works on a
  static ball but yields too many false positives from shoes, court lines and the
  referee stand to be decisive on moving play.

Consequence: a full pass would need ~2 images per point over 196 points with per-point
anchor refinement. I could not complete that here, and a list of low-confidence guesses
would violate the task's own instruction that only genuine block points be listed.

## To finish
Either (a) tighten the rally-end anchor to ±0.5 s — a player-convergence or motion-drop
detector on the 4 fps frames is the obvious route — then one 0.1 s zoom sheet per point
decides it; or (b) build a real ball tracker: colour mask plus temporal differencing at
full resolution over the anchored window, which also gives the landing side directly.
Blocker/hitter jersey numbers are readable from the live wide shot at 4x upscale
(confirmed: USC libero #16 legible), so player attribution does not need replays.
