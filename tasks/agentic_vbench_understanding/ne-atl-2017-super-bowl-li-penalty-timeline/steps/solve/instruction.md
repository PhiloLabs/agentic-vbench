# Super Bowl LI — Penalty Timeline Reconstruction

You are given one video at `/workspace/materials/game.mp4`: the full broadcast of
Super Bowl LI (New England Patriots vs Atlanta Falcons). Reconstruct the timeline of
every **referee-announced player foul** in the game.

A *referee-announced player foul* is a penalty for which the referee announces a
specific player's jersey number over the field microphone (for example, "Holding,
number 70, offense"). Team fouls that carry no announced jersey number — such as delay
of game or illegal formation — are **not** part of this task; do not report them.

For each foul, report the quarter, the game clock at the moment the foul occurred, the
infraction type, the jersey number of the penalised player, and their team. Use any
tools in the image (for example `ffmpeg` and `ffprobe`) to seek through, sample frames
from, and extract audio from the video. The referee's announcement, the on-screen
score-and-clock graphic, and the play action are your evidence.

## What to submit

Write `/workspace/output/solution.json` in exactly this shape:

```json
{
  "penalties": [
    {"quarter": 3, "clock": "1:30", "type": "offensive holding", "player_number": 70, "team": "ATL"},
    {"quarter": 2, "clock": "8:02", "type": "defensive holding", "player_number": 23, "team": "ATL"}
  ]
}
```

- One entry per referee-announced player foul, in any order.
- `quarter`: 1 to 4, or 5 for overtime.
- `clock`: the game clock shown on the broadcast when the foul occurred, as `mm:ss`.
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
