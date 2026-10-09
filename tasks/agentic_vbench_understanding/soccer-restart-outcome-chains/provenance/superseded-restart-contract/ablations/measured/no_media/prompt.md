# Soccer Restart-Outcome Chains

You are given NO video and NO images, and you have NO tools. The video is the full
broadcast of one Bundesliga match as a single clip, 6426.5 seconds long. Answer from
what you already know. You must still produce a complete answer in the schema below: an
empty sequence is not an acceptable response, so give your best guess.

Time `t` is seconds from the start of the clip. The first half runs from about `t = 350`
to about `t = 3225`, and the second half from about `t = 3400` to about `t = 6210`. The
players' kits, the run of play, and where the ball is put back into play are your
evidence.

## What to submit

Print the JSON object and nothing else as your final message, in exactly this shape:

```json
{
  "sequence": [
    {"t": 1200, "restart_type": 1, "team": "home", "outcome": 0},
    {"t": 4410, "restart_type": 3, "team": "away", "outcome": 1}
  ]
}
```

One entry per visible restart, in chronological order. Fields:

- `t`: the restart's time in seconds from the start of the clip (integer). A predicted
  restart counts only if its `t` is within 3 seconds of the true restart, so pin each
  one carefully.
- `restart_type`: one of
  - `1` = Throw-in
  - `2` = Corner
  - `3` = Direct free-kick
  - `4` = Indirect free-kick
- `team`: which side takes the restart, `"home"` or `"away"`. Home is the team named
  first in the on-screen score graphic; infer the two kits and keep the mapping
  consistent for the whole match.
- `outcome`: what the play following the restart produces, by either side:
  - `2` if a goal is scored within 30 seconds of the restart,
  - else `1` if a shot (on or off target) happens within 15 seconds of it,
  - else `0`.

## Rules

- Stay inside this working directory. Do not read, write, or search outside it.
- Do not look anything up online, and do not rely on memory of this match; find every
  restart in the video.
- Count only restarts that are actually visible in the broadcast (the ball being put
  back into play on screen). Kickoffs and goal-kicks are not scored restart types.
