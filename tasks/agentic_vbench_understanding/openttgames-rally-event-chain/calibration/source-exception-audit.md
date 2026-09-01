# Source-terminal exception audit

The benchmark ground truth is derived from the commit-pinned Extended OpenTTGames
annotation for `game_2`.

Six serve-defined windows contain real live-play exchanges in the official video
but have no supported terminal annotation in the pinned source annotation.
In response to maintainer review these six source-terminal gaps -- and only these
six -- were manually video-audited. Recording the audit is what the review asked
for; whether the resulting endings are accepted is the maintainer's call.

Within the rally segments that remain in the benchmark, the source-provided stroke
sequences were retained unchanged and only the missing terminal event was completed.
The one place where source strokes were dropped rather than kept is the rally 8
video-gap truncation described below.

| Rally ID | Serve time (s) | Source state | Video-audited terminal | Ending anchor (s) |
|---:|---:|---|---|---:|
| 13 | 195.158 | No supported terminal label after the source strokes | Left player's return lands on the right side; the right player then catches the ball by hand -> `left_winner` | 197.583 |
| 16 | 218.792 | No supported terminal label after the source strokes | Right player's return ends the point when the left player does not make a legal return and catches/stops the ball -> `right_winner` | 220.767 |
| 18 | 236.108 | No supported terminal label after the source strokes | Left player's final return is stopped by the net -> `left_net` | 239.833 |
| 24 | 331.967 | No supported terminal label after the serve | Right player's serve is stopped by the net -> `right_net` | 332.200 |
| 55 | 771.217 | No supported terminal label after the source strokes | Right player's return fails to cross the net -> `right_net` | 772.933 |
| 73 | 1057.983 | No supported terminal label after the source strokes | Left player's return lands on the right side; the right player then catches the ball by hand -> `left_winner` | 1059.367 |

## Video-gap truncation: rally 8

Serve window 8 (serve at frame 12155, 101.292 s) spans **two distinct points**,
not one. The scoreboard read from the official video moves from 4:3 at
t=100.0/102.5/103.3/104.0 to 4:4 at t=106.0 and stays there through t=118.0, so
a point was scored and recorded inside the gap that follows the first point.

**First point (kept).** The left player's loop at 102.433 s never crosses the net:
the source annotation records no `net` event after it, only two bounces on the
striking player's own side (102.950 s and 103.192 s). The terminal is therefore
`left_net`, and the anchor follows the `net` rule frozen in
`steps/solve/instruction.md` — the frame at which the ball is stopped by the net.

That frame was located by tracking the ball itself rather than by eye. Thirty
consecutive 120 fps frames (102.550–102.792 s) were extracted as 8-bit grayscale
over the crop x∈[480,1100), y∈[530,760); a per-pixel median across those frames
gives the static background, and the ball is the connected set of pixels
exceeding that background by more than 60 levels. The resulting centroid track:

| frame | time (s) | ball x (px) | advance (px) | blob (px) |
|---:|---:|---:|---:|---:|
| 12322 | 102.683 | 958.0 | +15.1 | 176 |
| 12323 | 102.692 | 972.8 | +14.8 | 174 |
| 12324 | 102.700 | 986.7 | +13.9 | 149 |
| **12325** | **102.708** | **994.0** | **+7.3** | **26** |
| 12326 | 102.717 | — | — | 0 (occluded) |
| 12327 | 102.725 | 996.0 | +2.0 | 3 |
| 12328 | 102.733 | 995.1 | −0.9 | 19 |
| 12329 | 102.742 | 995.2 | +0.1 | 67 |
| 12330 | 102.750 | 994.8 | −0.4 | 135 |
| 12331 | 102.758 | 993.6 | −1.2 | 155 |
| 12335 | 102.792 | 992.1 | — | 241 |

The ball advances at a steady 14–15 px per frame up to and including frame 12324.
At **frame 12325** the advance halves to 7.3 px and the visible blob collapses to
26 px as the ball enters the net; frame 12326 is fully occluded. From frame 12327
onward the x coordinate is pinned at 992–996 px and never advances again — the
ball's forward motion has been arrested and it drops onto the striking player's
own side, producing the source-annotated bounces at 102.950 s and 103.192 s.

The ending anchor is therefore **frame 12325 (102.708 s)**: the first frame at
which the net measurably arrests the ball. The later 102.950 s bounce is *not*
used, because the frozen contract anchors a `net` terminal on the net contact,
not on the subsequent bounce.

**Second point (excluded).** A new serve by the right player is visible: the ball
toss is tracked across 111.600–111.708 s and the ball is gone from the frame by
111.717 s. The racket-ball contact frame itself is not resolvable in the source
video, and the serving hand cannot be determined from the visible pre- and
post-contact frames. Rather than assign an inferred serve timestamp, player-hand
value, or stroke label, this point is excluded in full: 12 strokes across frames
13429–14690 and the `left_net` terminal at frame 14715. It is recorded in the
generated reference under `excluded` with `kind: video-gap`.

No other serve window is truncated.

## Candidates examined and rejected

Cross-referencing stroke events against the source's own `net` and `bounce`
events surfaced 26 windows where two consecutive strokes carry the same player
prefix, which is physically impossible in table tennis and implies an
unannotated opponent contact. Frame inspection at the estimated contact time
classified them as follows:

- **23 off-frame.** The camera framing is narrower than the playing area; when a
  player retreats to return a ball he leaves the frame entirely. These contacts
  are not observable in the media, so they are not added to the benchmark, and
  `steps/solve/instruction.md` now states that only visibly observable contacts
  are to be reported.
- **3 candidates examined individually** at 1/120 s across the full contact
  window (rally 32 ≈434.62 s, rally 65 ≈934.86 s, rally 67 ≈967.98 s). Final
  manual review found no clear racket-ball contact that could be labelled with
  confidence for any of them: rally 32 and rally 67 show no distinguishable
  opponent contact, and in rally 65 the striker is cut off at the frame edge with
  the torso outside the frame, leaving the hand unresolvable. **None were added**,
  and no player, hand, or stroke label was assigned to any of them.

The full anomaly inventory, including per-row intervening `net`/`bounce`
timestamps and contact windows, was produced during this audit and is not
required to regenerate the benchmark.

## Scope

This is a bounded exception audit, not a relabeling pass over the benchmark.

The six terminal completions above and the single rally 8 truncation are the only
manual interventions on the commit-pinned source annotation. **No stroke was
added to the benchmark.** All 387 benchmark strokes remain source-derived.

The video audit used the official `game_2.mp4` media corresponding to the
benchmark source. Ending anchors were selected through fine-grained frame
inspection and mapped to the benchmark's 120 fps video timeline.

After applying the six terminal exceptions and the rally 8 truncation, the
generated benchmark contains 92 valid rallies, 387 source-derived strokes, one
documented video-gap exclusion (12 strokes), and zero silently excluded
serve-defined windows.
