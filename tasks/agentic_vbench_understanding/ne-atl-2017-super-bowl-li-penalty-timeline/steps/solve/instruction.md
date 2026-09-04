# Super Bowl LI — Penalty Timeline Reconstruction

You are given one video at `/workspace/materials/game.mp4`: the full broadcast of
Super Bowl LI (New England Patriots vs Atlanta Falcons). Reconstruct the timeline of
every **referee-announced player foul** in the game.

A *referee-announced player foul* is a penalty for which the referee announces a
specific player's jersey number over the field microphone (for example, "Holding,
number [N], offense"). Team fouls that carry no announced jersey number — such as delay
of game or illegal formation — are **not** part of this task; do not report them.

For each foul, report the quarter, the game clock (defined below), the infraction type,
the jersey number of the penalised player, and their team. Use any tools in the image
(for example `ffmpeg`/`ffprobe`, and `faster-whisper` for transcribing the referee's
audio) to seek through, sample frames from, extract audio from, and transcribe the
video. The referee's announcement, the on-screen score-and-clock graphic, and the play
action are your evidence.

## What to submit

Write `/workspace/output/solution.json` in exactly this shape:

```json
{
  "penalties": [
    {"quarter": 1, "clock": "5:00", "type": "false start", "player_number": 99, "team": "NE"},
    {"quarter": 4, "clock": "2:15", "type": "unnecessary roughness", "player_number": 50, "team": "ATL"}
  ]
}
```

(The two rows above are formatting examples only, not real fouls from this game.)

- One entry per referee-announced player foul, in any order.
- `quarter`: 1 to 4, or 5 for overtime.
- `clock`: the game clock shown in the on-screen score bug on the **last frame it is
  displayed before the referee begins the foul announcement**. The score bug is hidden
  during live action and restored between plays, so use that specific frame — not the
  time when the play ended, the down-and-distance display, or any other moment.
- `type`: the infraction, lower-case, from this closed vocabulary — `offensive holding`,
  `defensive holding`, `offensive pass interference`, `defensive pass interference`,
  `false start`, `defensive offside`, `illegal contact`, `illegal use of hands`,
  `unnecessary roughness`, `roughing the passer`.
- `player_number`: the jersey number announced by the referee, as an integer.
- `team`: `NE` or `ATL`.

## Rules

- Stay inside this working directory. Do not read, write, or search outside it.
- Do not look anything up online, and do not rely on memory of this game; find every
  foul in the video.
- Report only referee-announced player fouls, as defined above. Do not report team
  fouls that carry no announced jersey number.
