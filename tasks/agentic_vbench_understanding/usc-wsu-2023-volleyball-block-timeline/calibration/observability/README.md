# Observability ledger

Two questions, answered separately from the shipped 720p video and independently of any
agent output:

1. **When is each point awarded?** — `flips.json` / `flips.md`, all 23 confirmed.
2. **Can each name the scorer asks for be seen?** — `witness.md`, field by field, with a
   frame strip per event in `witness/`.

## When each point is awarded

`flips.json` and `flips.md` give, for all 23 block points, the second at which the
broadcast score bug flips to the post-point score. The two numerals of the bug are OCR'd
(tesseract, `--psm 6`, binarised at 120, with a black margin added because strokes
touching the crop edge are misread as an extra digit), a 20 s coarse pass builds the
score-versus-time curve, each target score is bisected to ~0.5 s, and the bug is then
re-read at the result to confirm it shows exactly that score. **All 23 confirm**, and
the file records the read-back per event.

Cross-check: an independent Opus 5 calibration run, which reconstructed the whole
200-rally timeline by template-matching the same bug, put the first block point at
283.2 s against 286.9 s here — consistent within the close-up delay.

## Whether each name is visible

`witness.md` is the per-field table: for every event, every credited blocker and the
blocked hitter, what is legible in the post-point window and at which offset. The
headline numbers:

| | events |
|---|---|
| every credited blocker legible | **11 / 23** |
| some credited blockers legible | 4 / 23 |
| no credited blocker legible | 8 / 23 |
| blocked hitter legible | **1 / 23** |
| blocked hitter plausible but occluded | 2 / 23 |
| blocked hitter not legible | 20 / 23 |

Where a number is legible it matches the answer key; no event was found where the video
contradicts the official record.

## What the broadcast does

- **During the rally the wide sideline shot never resolves jersey numbers.** Players are
  40-80 px tall; the ball is 15-40 px and usually motion-blurred.
- **There is no replay.** After a point the feed cuts to whoever is celebrating, or to
  the next server — never to a slow-motion of the play.
- **The cut to a net close-up is where numbers become readable**, and it follows some
  points but not all. On the eight events with nothing legible, two are set-winning
  points where the feed goes to the crowd or the changeover, and on the rest the camera
  stays wide or follows the team that did not make the block.
- **The close-up favours the blocking side**, which is why the stuffed hitter is the
  field that almost never resolves.

`sheets/` holds an earlier four-frame montage per event at reduced width; `witness/`
supersedes it for reading numbers and is what `witness.md` cites.
