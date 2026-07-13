# Soccer Restart-Outcome Chains

You are given one video at `/workspace/materials/game.mp4`: a full 90-minute soccer
broadcast (Bundesliga), both halves concatenated into a single clip. Reconstruct the
complete timeline of every **visible ball restart** in the match, and for each one, the
chain of play it starts.

Time `t` is seconds from the start of the clip. The first half is roughly `t` in
`[0, 2699]` and the second half follows it. Use any tools in the image (for example
`ffmpeg` and `ffprobe`) to seek through and sample the video. The players' kits, the
run of play, and where the ball is put back into play are your evidence.

## What to submit

Write `/workspace/output/solution.json` in exactly this shape:

```json
{
  "sequence": [
    {"t": 800, "restart_type": 1, "team": "home", "outcome": 0},
    {"t": 1362, "restart_type": 3, "team": "away", "outcome": 1}
  ]
}
```

One entry per visible restart, in chronological order. Fields:

- `t`: the restart's time in seconds from the start of the clip (integer).
- `restart_type`: one of
  - `1` = Throw-in
  - `2` = Corner
  - `3` = Direct free-kick
  - `4` = Indirect free-kick
- `team`: which side takes the restart, `"home"` or `"away"`. Home is the side
  defending the scoreboard's left at kickoff; infer the two kits and keep the mapping
  consistent for the whole match.
- `outcome`: the chain the restart starts, judged from the following play:
  - `2` if the team that took the restart scores within 30 seconds of it,
  - else `1` if a shot (on or off target) happens within 15 seconds of it,
  - else `0`.

## Rules

- Stay inside this working directory. Do not read, write, or search outside it.
- Do not look anything up online, and do not rely on memory of this match; find every
  restart in the video.
- Count only restarts that are actually visible in the broadcast (the ball being put
  back into play on screen). Kickoffs and goal-kicks are not scored restart types.
