# Reconstruct the Break-Point Ledger

You are given the complete 2023 US Open match between Daniil Medvedev and Alex De
Minaur at `/workspace/materials/match.mp4`.

Reconstruct every break-point opportunity in the match. A break point is a point
where the receiver can win the current game by winning that point. Report repeated
break points in the same game separately and in chronological order.

Use the video as your evidence. Do not look up the match online or rely on outside
knowledge.

## What to submit

Write `/workspace/output/solution.json` in exactly this shape:

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
      "rally_shots": 8,
      "terminal_player": "Daniil Medvedev",
      "terminal_stroke": "forehand_groundstroke",
      "terminal_court_position": "baseline",
      "terminal_result": "winner",
      "terminal_error": "none"
    }
  ]
}
```

- Record the game and point scores immediately before the break point begins.
- Scores are player-specific, regardless of which player is serving.
- Point-score values are `0`, `15`, `30`, `40`, or `AD`.
- `server` is exactly `Daniil Medvedev` or `Alex De Minaur`.
- `opportunity` starts at `1` in each service game and increments for every break
  point in that game.
- `first_serve_in` is `true` when the point begins with a legal first serve and
  `false` when a first-serve fault requires a second serve.
- `outcome` is `converted` when the receiver wins the point and therefore the game;
  otherwise it is `saved`.
- `serve_direction` describes the serve that starts the live point: `wide`, `body`,
  `down_the_t`, or `unknown`. If the first serve is a fault, describe the second serve.
- `rally_shots` counts the serve and all successful returns or rally strokes. Include
  a point-ending winner, ace, or unreturnable serve; exclude a point-ending error
  stroke. An ace therefore has a count of `1`.
- `terminal_player` is exactly `Daniil Medvedev` or `Alex De Minaur` and identifies
  the player who made the point-ending contact. For an ace or unreturnable serve,
  this is the server.
- `terminal_stroke` is one of `serve`, `forehand_groundstroke`,
  `backhand_groundstroke`, `forehand_slice`, `backhand_slice`, `forehand_volley`,
  `backhand_volley`, `forehand_half_volley`, `backhand_half_volley`,
  `forehand_swinging_volley`, `backhand_swinging_volley`, `forehand_drop_shot`,
  `backhand_drop_shot`, `forehand_lob`, `backhand_lob`, `overhead`,
  `backhand_overhead`, `trick_shot`, or `unknown`.
- `terminal_court_position` is `baseline`, `net`, or `serve`. Use `serve` only when
  the serve itself ends the point. Classify the hitter's position, not where the
  ball lands.
- `terminal_result` is `winner`, `forced_error`, `unforced_error`, `ace`, or
  `unreturnable`.
- `terminal_error` is `net`, `wide`, `deep`, `wide_and_deep`, `shank`, `unknown`,
  or `none`. Use `none` unless `terminal_result` is an error.

Treat ordinary forehand and backhand groundstrokes as `*_groundstroke`. Use
`*_slice` only for a visibly sliced or chipped stroke; do not infer topspin versus
flat when the broadcast does not establish it.
