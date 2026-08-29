# Observability ledger

Purpose: establish, from the shipped 720p video alone, that the fields the scorer asks
for are actually there — so that a low agent score means the task is hard rather than
impossible.

## How each point was located

`flips.json` / `flips.md` give, for all 23 block points, the second at which the
broadcast score bug flips to the post-point score — i.e. when the point is awarded.
These were derived verifier-side and independently of any agent output: the two
numerals of the score bug are OCR'd (tesseract, `--psm 6`, binarised at 120, with a
black margin added because strokes touching the crop edge are misread as an extra
digit), a 20 s coarse pass builds the score-versus-time curve, and each target score
is then bisected to ~0.5 s and re-read to confirm the bug shows exactly that score.
The two set-winning points and one point where the sides do not reach the target
simultaneously needed a directed scan; **all 23 are confirmed**, and every sheet in
`sheets/` carries the score bug in frame, so the anchor of each event can be checked
by eye.

Cross-check: an independent Opus 5 calibration run, which reconstructed the whole
200-rally timeline by template-matching the same bug, put the first block point at
283.2 s against 286.9 s here — consistent within the close-up delay.

## What the broadcast shows, and when

- **During the rally the wide sideline shot never resolves jersey numbers.** Players
  are 40-80 px tall; the ball is 15-40 px and usually motion-blurred. This holds on
  every event examined.
- **There is no replay.** After a point the feed cuts to the next server or stays
  wide; it never cuts to a slow-motion of the play.
- **After some points the feed cuts to a net close-up**, where numbers are large and
  sharp. Where that cut happens it is the one place a number can simply be read.
- **It does not happen after every point.** On set 1 at 14-10 and set 1 at 23-15 the
  feed stays on the wide shot through the whole post-point window, so nothing is
  directly legible there.

That split is the crux of the task's difficulty. Where a close-up exists it is short —
the camera pans and the credited players enter and leave the shot inside it — and
where it does not, a number cannot be read at all and the players have to be carried
forward from an earlier close-up through the rotation.

## Per-event verification

`sheets/` holds, for every one of the 23 points, four frames spanning the post-point
window (t+0.8, +1.6, +2.4, +3.2 relative to the flip), full frame at source
resolution.

Read directly from those sheets, four frames each:

| event | credited blockers | read off the close-up |
|---|---|---|
| set 1, 4-2 | Tuaniga, Miller | **91 and 10** — both, sharp |
| set 1, 14-10 | Miller | blocked hitter **15** (Jehlarova) legible; blocker not in shot |
| set 1, 23-15 | Ariail, K. Williams | **13 and 8** at t+3.2 when the shot widens |
| set 2, 16-10 | Jehlarova, Ung | **15 and 12** — both, sharp |
| set 3, 13-17 | Jehlarova, Ung | **15 and 12** — both, sharp |
| set 4, 10-8 | Ryan, Radakovic | **8 and 21** — both, sharp |

Spot-checked at t+1.6 only (one frame, not the window):

| event | credited blockers | at t+1.6 |
|---|---|---|
| set 2, 2-1 | Miller, Fields | **10 and 5** visible |
| set 3, 1-6 | Jehlarova, Ung | **15** visible; 12 out of shot at this instant |
| set 1, 25-15 | K. Williams, Ariail | opposing side in shot; not legible at this instant |
| set 2, 10-7 | Ariail | still the wide shot at this instant; not legible |

## Findings

- **Every event's anchor is verified.** Set and exact score-after — the fields the
  scorer matches on before it looks at any name — are confirmed for all 23 from the
  score bug itself.
- **Where a close-up follows the point, the credited blockers are legible**, and on
  every event examined that way the numbers matched the answer key exactly.
- **The blocked hitter is legible less often.** The close-up follows the players at
  the net, which usually favours the side that won the point. The scorer already
  treats this as the harder half: a wrong or missing hitter with the blockers exact
  earns partial credit rather than nothing.
- **Direct legibility is not universal.** On the events checked where the feed stays
  wide, no jersey can be read in the post-point window at all. Identification there
  depends on carrying players forward from an earlier close-up rather than reading a
  number in the moment.
- No event was found where the ground truth names a player who cannot be seen at all,
  so nothing in the answer key is unsupported by the video.

What this ledger does not yet contain is a frame-level witness for **each** credited
name on **all** 23 events; the table above is the subset examined directly.
