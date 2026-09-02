# Block Timeline Reconstruction

You are given one video at `/workspace/materials/match.mp4`: the full broadcast of a
college women's volleyball match (Southern California at Washington State, five sets).
The video has no audio track. Find every point in the match that ended as a **block**,
by either team.

For each block point, report the set, the score immediately after the point, the
player(s) credited with the block, and the opposing hitter who was blocked. Use any
tools in the image (for example `ffmpeg` and `ffprobe`) to seek through and sample the
video. The on-screen score graphic, the players' jersey numbers, and the play action
are your evidence. The rosters below map jersey numbers to names.

## What to submit

Write `/workspace/output/solution.json` in exactly this shape:

```json
{
  "events": [
    {"set": 2, "score_after": "5-9",   "type": "block", "players": ["First Last", "First Last"], "blocked": "First Last"},
    {"set": 4, "score_after": "21-18", "type": "block", "players": ["First Last"], "blocked": "First Last"}
  ]
}
```

- One entry per block point, in any order.
- `set`: 1 to 5.
- `score_after`: the score right after the point, written `USC-WashingtonState` —
  the same order the broadcast score graphic displays (USC, the visitor, on the
  left; Washington State, the home team, on the right).
- `type`: always `"block"` — the point ended at the net off a block (the officially
  scored block point, not a block touch the attacker still kills through, and not a
  deflection that stayed in play). Serve aces, attack errors, and other rally endings
  are not block points and must not be listed.
- `players`: the credited blocker or blockers (one or two names, order does not
  matter). Credit follows the official scorer's rules: a stuff by one player is one
  name; a block shared by two players at the net is two names.
- `blocked`: the opposing hitter who was blocked — the player whose attack the block
  stopped (one name, on the team opposite the blockers). Required for every entry.

## Rosters (jersey number → name)

Southern California (shown left on the score graphic):

| # | Name | | # | Name |
|---|---|---|---|---|
| 2 | London Wijay | | 13 | Tyrah Ariail |
| 4 | Megan Verbiest | | 16 | Gala Trubint |
| 5 | Skylar Fields | | 22 | Rylie McGinest |
| 6 | Ellie Snook | | 91 | Mia Tuaniga |
| 8 | Kalyah Williams | | | |
| 10 | Lindsey Miller | | | |

Washington State (shown right on the score graphic):

| # | Name | | # | Name |
|---|---|---|---|---|
| 3 | Karly Basham | | 11 | Julia Norville |
| 4 | Logann Golden | | 12 | Argentina Ung |
| 5 | Iman Isanovic | | 15 | Magda Jehlarova |
| 7 | Pia Timmer | | 16 | Weronika Wojdyla |
| 8 | Katy Ryan | | 21 | Lana Radakovic |
| 9 | Shea Rubright | | | |

## Rules

- Stay inside this working directory. Do not read, write, or search outside it.
- Do not look anything up online, and do not rely on memory of this match; find every
  qualifying point in the video.
- Report only points that ended as a block: kills (including a kill driven through a
  block touch), service aces, attack errors, service errors, and other rally endings
  are not entries.

## How to reach the video in this run

The broadcast is inside the task environment, not in this directory. Run every command
that touches it through the `./run` wrapper, which executes inside that environment:

    ./run ffprobe -v error -show_entries format=duration -of csv=p=0 /workspace/materials/match.mp4
    ./run ffmpeg -y -ss 3600 -i /workspace/materials/match.mp4 -frames:v 1 shot.jpg

Your working directory here is shared with the environment as `/workspace/work`, so a
file you write there with `./run` appears beside this instruction and you can open it.
The environment has ffmpeg, ffprobe, tesseract, ImageMagick, Python 3 with NumPy and
Pillow, and no network. Write your answer to ./output/solution.json as described above.
