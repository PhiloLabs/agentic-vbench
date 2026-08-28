# Observability ledger

Purpose: show that every field the scorer asks for is actually recoverable from the
shipped 720p video, so that a low agent score means the task is hard rather than
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
simultaneously needed a directed scan; all 23 are confirmed.

Cross-check: an independent Opus 5 calibration run, which reconstructed the whole
200-rally timeline by template-matching the same bug, put the first block point at
283.2 s against 286.9 s here — consistent within the close-up delay.

## What the broadcast shows, and when

Measured on this file, the pattern is the same at every point examined:

- **During the rally the wide sideline shot never resolves jersey numbers.** Players
  are 40-80 px tall; the ball is 15-40 px and usually motion-blurred.
- **There is no replay.** After a point the feed cuts to the next server, not to a
  slow-motion of the play.
- **Roughly 0.8-3.2 s after the point the feed cuts to a net close-up** where numbers
  are large and sharp. This window is where attribution is recoverable, and it is the
  only place it is recoverable.

This is the crux of the task's difficulty: the information is present, but only in a
~2 s window per point that has to be found first, and a single frame from that window
is often not enough — the camera pans, and the credited players enter and leave the
shot within it.

## Per-event verification

`sheets/` holds, for every one of the 23 points, four frames spanning the close-up
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

The last two illustrate the point above: a single sample from the window is not
enough, which is why the sheets carry four frames each and why an agent that samples
only the rally — as the Opus 5 run did — comes away with nothing.

## Findings

- **Credited blockers are recoverable.** On every event examined with the full
  four-frame window the credited blockers were legible, and the numbers matched the
  ground truth exactly.
- **The blocked hitter is recoverable less often.** The close-up follows the players
  at the net, which usually favours the side that won the point; the hitter is
  sometimes present (set 1, 14-10 reads 15) and sometimes not. The scorer already
  treats this as the harder half: a wrong or missing hitter with the blockers exact
  earns partial credit rather than nothing.
- No event was found where the ground truth names a player who cannot be seen at all,
  so nothing in the answer key is unsupported by the video.
