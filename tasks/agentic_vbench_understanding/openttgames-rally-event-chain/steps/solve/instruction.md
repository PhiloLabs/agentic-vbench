# Full-match table-tennis rally event-chain reconstruction

Analyze the complete table-tennis match at:

`/workspace/materials/game.mp4`

Reconstruct the ordered stroke chain and terminal outcome for every live-play
rally in the match.

Use local tools such as FFmpeg, ffprobe, scripts, and frame extraction.
Inspect the full video. Do not use the Internet, pre-existing annotations,
or files outside `/workspace`.

## Rally and player conventions

- A rally begins at the server's racket-ball contact and ends at the first
  supported terminal event.
- Count the serve as the first stroke.
- A stroke is a live-play racket-ball contact intended to serve or return the
  ball.
- Do not count warm-ups, dead-ball swings, ball handling between points, or
  other non-live-play actions.
- Report only racket-ball contacts you can actually observe in the video. The
  camera framing is narrower than the playing area, and a player who moves back
  to return a ball may leave the frame entirely. Do not infer or report a contact
  that occurs outside the camera frame, even when the ball's later path implies
  one must have happened. The same applies to a contact whose moment is not
  visible in the footage.
- Where a contact is observable but one of its categorical fields is not, do not
  guess: omit the whole stroke rather than report it with an inferred `player`,
  `hand`, or `stroke` value.
- Player identity is determined by fixed image position:
  - `left`: the player positioned on the left side of the table in the video.
  - `right`: the player positioned on the right side of the table in the video.
- Reconstruct every live-play rally in the match whose serve contact you can
  observe. A rally is anchored on its serve, so if a point is played but its
  serve's racket-ball contact is not visible in the footage, omit that rally
  entirely rather than reporting it with an estimated serve time.
- Report rallies in chronological order by serve time.
- Report strokes within each rally in chronological order.

## Hand classification

`hand` must be exactly one of:

- `forehand`: the player contacts the ball using a forehand stroke orientation,
  with the racket swung from the racket-hand side of the body.
- `backhand`: the player contacts the ball using a backhand stroke orientation,
  with the racket presented across or in front of the body using a backhand
  stroke motion.

Classify forehand/backhand from the visible stroke motion, not from whether the
player appears on the left or right side of the image.

## Stroke technique classification

`stroke` must be exactly one of:

- `serve`: the initial racket-ball contact that starts the rally.
- `loop`: an attacking topspin stroke with a pronounced forward/upward brushing
  swing.
- `block`: a compact reactive return that primarily redirects the opponent's
  pace, usually with little backswing.
- `push`: a controlled underspin/backspin return produced with an open racket
  and a short forward/downward stroke.
- `flick`: a quick attacking stroke against a short ball, typically played
  close to or over the table with a compact wrist/forearm action.
- `lob`: a high-arcing defensive return intended to send the ball high and deep.
- `smash`: a forceful attacking stroke, usually relatively flat and directed
  strongly forward/downward against a high or attackable ball.
- `chop`: a defensive slicing stroke with a pronounced downward motion that
  imparts backspin.

## Rally-ending convention

Every ending label has the form:

`<player>_<ending-category>`

The `left` or `right` prefix identifies the player whose action or failure
causes that terminal outcome.

The ending categories are:

- `net`: the prefixed player strikes the ball and it is stopped by the net, or
  touches the net and clearly returns to that same player's side.
- `not_hitting_ball`: the prefixed player is the receiving player who attempts
  to play the ball but fails to make racket contact.
- `winner`: the prefixed player hits a legal shot that becomes unreachable for
  the opponent.
- `double_bounce`: the prefixed player hits a legal shot that bounces twice on
  the opponent's side before the opponent returns it.
- `out`: the prefixed player sends the ball beyond the opponent's side without
  a legal table bounce.
- `miss_on_own_side`: after the prefixed player's racket contact, the ball falls
  below the table on that same player's side.

The allowed ending labels are exactly:

- `left_out`
- `right_out`
- `left_net`
- `right_net`
- `left_winner`
- `right_winner`
- `left_double_bounce`
- `right_double_bounce`
- `left_not_hitting_ball`
- `right_not_hitting_ball`
- `left_miss_on_own_side`
- `right_miss_on_own_side`

### Net-contact rule

A ball touching the net is not automatically a rally ending.

- If the ball touches the net and still lands legally on the opponent's side,
  play continues.
- If the ball is stopped by the net or clearly returns toward the striking
  player's own side, use `<player>_net`.
- If the ball touches the net and then continues out of play, classify the
  terminal outcome according to where the ball ultimately goes, such as `out`
  or `miss_on_own_side`.

## Timestamp anchors

All timestamps are seconds from the first video frame.

- `serve_time_sec`: timestamp of the server's racket-ball contact.
- stroke `time_sec`: timestamp of that stroke's racket-ball contact.
- `ending_time_sec`: timestamp of the observable terminal event using the
  category-specific rule below:
  - `net`: when the ball is stopped by the net, or when net contact makes it
    clear that the ball will return to the striking player's own side.
  - `not_hitting_ball`: when the receiving player has failed to make racket
    contact and the ball has passed that player's playable racket position.
  - `winner`: when the ball becomes unreachable for the receiving player. If
    the ball contacts or is caught by the receiving player before another clear
    unreachable point, use that contact as the observable anchor.
  - `double_bounce`: at the second bounce on the receiving player's side. This
    is the benchmark's operational timestamp anchor for this category.
  - `out`: when the ball has fully passed the table boundary on the opponent's
    side without a legal table bounce.
  - `miss_on_own_side`: when the ball has fully dipped below the table on the
    striking player's own side.

## Required output

Write valid JSON to:

`/workspace/output/solution.json`

Use this schema:

```json
{
  "rallies": [
    {
      "serve_time_sec": 5000.000,
      "strokes": [
        {
          "time_sec": 5000.000,
          "player": "right",
          "hand": "forehand",
          "stroke": "serve"
        },
        {
          "time_sec": 5000.700,
          "player": "left",
          "hand": "backhand",
          "stroke": "push"
        }
      ],
      "ending_time_sec": 5001.600,
      "ending": "left_out"
    }
  ]
}
```
The numeric values in this example are synthetic schema examples only and lie
outside the duration of the provided video.

## Evaluation tolerances

- `serve_time_sec`: within 1.0 second of the serve contact.
- each stroke `time_sec`: within 0.35 seconds of the racket contact.
- `ending_time_sec`: within 1.0 second of the terminal rally event.

Categorical fields must use exactly the vocabulary defined above.