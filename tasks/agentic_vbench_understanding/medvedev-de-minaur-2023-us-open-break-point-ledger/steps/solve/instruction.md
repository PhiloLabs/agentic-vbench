# Reconstruct the Break-Point Ledger

You are given the complete 2023 US Open match between Daniil Medvedev and Alex De
Minaur at `/workspace/materials/match.mp4`.

Reconstruct every break-point opportunity in the match. A break point is a point
where the receiver can win the current game by winning that point. Report repeated
break points in the same game separately and in chronological order.

Use the silent video as your evidence. The supplied file has no audio track. Do not
look up the match online or rely on outside knowledge.

## What to submit

Write `/workspace/output/solution.json` using this required shape. The values below
are a hypothetical format example, not an answer drawn from the match:

```json
{
  "break_points": [
    {
      "set": 1,
      "medvedev_games": 1,
      "de_minaur_games": 0,
      "medvedev_points": "40",
      "de_minaur_points": "15",
      "server": "Alex De Minaur",
      "opportunity": 1,
      "first_serve_in": false,
      "outcome": "converted",
      "serve_direction": "wide",
      "rally_shots": 2,
      "terminal_player": "Alex De Minaur",
      "terminal_stroke": "forehand_groundstroke",
      "terminal_court_position": "baseline",
      "terminal_result": "unforced_error",
      "terminal_error": "net",
      "shots": [
        {"stroke": "serve", "direction": "wide"},
        {"stroke": "backhand_groundstroke", "direction": "middle"},
        {"stroke": "forehand_groundstroke", "direction": "receiver_backhand"}
      ]
    }
  ]
}
```

- Record the game and point scores immediately before the break point begins.
- Scores are player-specific, regardless of which player is serving.
- `set` is a JSON integer from `1` through `4`. Both `*_games` fields are
  non-negative JSON integers; `opportunity` and `rally_shots` are positive JSON
  integers.
- Point-score values are the JSON strings `"0"`, `"15"`, `"30"`, `"40"`, or
  `"AD"`.
- `server` is exactly `Daniil Medvedev` or `Alex De Minaur`.
- `opportunity` starts at `1` in each service game and increments for every break
  point in that game.
- `first_serve_in` is `true` when the point begins with a legal first serve and
  `false` when a visible first-serve fault requires a second serve.
- `outcome` is `converted` when the receiver wins the point and therefore the game;
  otherwise it is `saved`.
- `serve_direction` describes the serve that starts the live point: `wide` travels
  toward the receiver's sideline, `body` travels through or immediately beside the
  receiver's starting position, `down_the_t` travels toward the center service line,
  and `unknown` means the broadcast view does not establish one of those directions.
  If the first serve is a fault, classify the second serve.
- `rally_shots` counts the serve and all successful returns or rally strokes. Include
  a point-ending winner, ace, or unreturnable serve; exclude a point-ending error
  stroke. An ace therefore has a count of `1`.
- `terminal_player` is exactly `Daniil Medvedev` or `Alex De Minaur` and identifies
  the player credited with the terminal result. For a non-serve winner or error,
  this is the hitter of the winning shot or error attempt. For an ace or
  unreturnable serve, it is the server.
- `terminal_stroke` is one of `serve`, `forehand_groundstroke`,
  `backhand_groundstroke`, `forehand_slice`, `backhand_slice`, `forehand_volley`,
  `backhand_volley`, `forehand_half_volley`, `backhand_half_volley`,
  `forehand_swinging_volley`, `backhand_swinging_volley`, `forehand_drop_shot`,
  `backhand_drop_shot`, `forehand_lob`, `backhand_lob`, `overhead`,
  `backhand_overhead`, `trick_shot`, or `unknown`.
- `terminal_court_position` is `baseline`, `net`, `serve`, or `unknown`. Use `net` when the
  hitter is at or inside the service line and `baseline` when the hitter is behind
  it. Use `serve` only when the serve itself ends the point. Classify the hitter's
  position, not where the ball lands. Use `unknown` only when the broadcast view
  does not establish the hitter's position.
- `terminal_result` is `winner`, `forced_error`, `unforced_error`, `error_unknown`,
  `ace`, or `unreturnable`, using the observable criteria below. Use
  `error_unknown` only for a visible non-serve miss when the broadcast does not
  establish enough pressure evidence to distinguish `forced_error` from
  `unforced_error`.
- `terminal_error` is `net`, `wide`, `deep`, `wide_and_deep`, `shank`, `unknown`,
  or `none`. For an error, use `shank` first when contact is visibly framed or a
  severe mishit. Otherwise use `net` when the ball fails to clear the net, `wide`
  when it lands beyond a sideline, `deep` when it lands beyond the baseline,
  `wide_and_deep` when both are clear, and `unknown` only when the miss location is
  not visible. Use `none` for `winner`, `ace`, and `unreturnable`.
- `shots` is the task's scored shot sequence in chronological order: the serve that
  begins live play, every successful return or rally stroke, a point-ending winner,
  and a point-ending error attempt. Omit a first-serve fault and start with the
  second serve. An unsuccessful receiver touch on an `unreturnable` serve is not a
  separate shot token.
- Every entry in `shots` has the required `stroke` and `direction` fields. The first entry uses
  `serve` as its stroke and one of `wide`, `body`, `down_the_t`, or `unknown` as its
  direction. Later entries use the same non-serve stroke vocabulary as
  `terminal_stroke` and one of `receiver_forehand`, `middle`,
  `receiver_backhand`, or `unknown` as their direction.
- For a non-serve shot, `receiver_forehand` means the ball travels toward the
  receiver's forehand-side 30% of the baseline, `middle` means the central 40%, and
  `receiver_backhand` means the receiver's backhand-side 30%. Classify where the
  ball crosses the receiver's baseline or, for a netted ball, drop shot, or other
  shot that ends earlier, where its visible trajectory would have crossed that
  baseline. Use `unknown` only when the view does not establish that projection.
- The server owns the first token in `shots`; the players then alternate for every
  non-serve token, so do not add a player or shot-number field to the shot objects.
- For a `winner`, `ace`, or `unreturnable`, `shots` has the same length as
  `rally_shots`. For a `forced_error`, `unforced_error`, or `error_unknown`, `shots`
  has one additional entry because `rally_shots` excludes the point-ending error
  attempt. An ace or unreturnable serve therefore has exactly one shot entry.

## Classifying the point-ending result

- `winner`: a non-serve shot lands legally and ends the point without a subsequent
  racket contact by the opponent.
- `forced_error`: the point-ending miss is made under immediate, visible pressure
  from the preceding shot. Observable pressure includes running or stretching to
  reach the ball, being jammed or pulled outside a normal contact zone, contacting
  while off balance, or having clearly reduced preparation time.
- `unforced_error`: the player reaches a controllable ball in a neutral position
  with stable balance, a normal contact zone, and reasonable preparation time, but
  still makes the point-ending miss.
- `error_unknown`: a visible non-serve miss for which the broadcast does not show
  enough of the preceding pressure, preparation, or contact to distinguish a
  forced error from an unforced error.
- `ace`: a legal serve ends the point without touching the receiver's racket.
- `unreturnable`: the legal serve touches the receiver's racket but produces no
  separately identifiable return attempt. A blocked or framed touch without a
  distinct return attempt is therefore
  `unreturnable`; record only the serve token. If the receiver makes an identifiable
  return attempt, classify a miss as `forced_error`, `unforced_error`, or
  `error_unknown` according to the visible pressure evidence, and include that error
  attempt in `shots`.

For both `ace` and `unreturnable`, report the server as `terminal_player`, `serve` as
`terminal_stroke`, and `serve` as `terminal_court_position`. Apply the categories in
this order: no racket touch is an `ace`; a touch without an identifiable return is
`unreturnable`; an identifiable return attempt that misses is a forced, unforced, or
unknown-pressure error according to the visible evidence.

Judge pressure only from visible play immediately before contact. Do not infer
`forced_error` or `unforced_error` from the score, the importance of the point, the
identity of the player, or the eventual game result.

Treat ordinary forehand and backhand groundstrokes as `*_groundstroke`. Use
`*_slice` only for a visibly sliced or chipped stroke; do not infer topspin versus
flat when the broadcast does not establish it. A `*_volley` is struck before the
bounce with a compact volley motion; a `*_half_volley` is struck immediately after
the bounce; and a `*_swinging_volley` is struck before the bounce with a full swing.
A `*_drop_shot` is intentionally played short and softly, while a `*_lob` is sent
high over an opponent. Use `overhead` or `backhand_overhead` for an above-head smash,
`trick_shot` only for a visibly unconventional contact that fits no listed stroke,
and `unknown` when the view does not support a listed category.
