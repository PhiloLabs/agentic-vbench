# Ace and Block Timeline Reconstruction

You are given one video at `/workspace/materials/match.mp4`: the full broadcast of a
college women's volleyball match (Southern California at Washington State, five sets).
The video has no audio track. Find every point in the match that ended as a **service
ace** or as a **block**, by either team.

For each such point, report the set, the score immediately after the point, whether
it was an ace or a block, and the player(s) credited. Use any tools in the image (for
example `ffmpeg` and `ffprobe`) to seek through and sample the video. The on-screen
score graphic, the players' jersey numbers, and the play action are your evidence.
The rosters below map jersey numbers to names.

## What to submit

Write `/workspace/output/solution.json` in exactly this shape:

```json
{
  "events": [
    {"set": 3, "score_after": "0-1",   "type": "ace",   "players": ["First Last"]},
    {"set": 1, "score_after": "4-2",   "type": "block", "players": ["First Last", "First Last"], "blocked": "First Last"}
  ]
}
```

- One entry per qualifying point, in any order.
- `set`: 1 to 5.
- `score_after`: the score right after the point, written `USC-WashingtonState` —
  the same order the broadcast score graphic displays (USC, the visitor, on the
  left; Washington State, the home team, on the right).
- `type`: `"ace"` — the serve scored directly (untouched, or unplayable off the
  receiver); `"block"` — the point ended at the net off a block (the officially
  scored block point, not a block touch the attacker still kills through, and not a
  deflection that stayed in play).
- `players`: for an ace, the server (one name). For a block, the credited blocker or
  blockers (one or two names, order does not matter). Credit follows the official
  scorer's rules: a stuff by one player is one name; a block shared by two players
  at the net is two names.
- `blocked`: **for a block only**, the opposing hitter who was blocked — the player
  whose attack the block stopped (one name, on the team opposite the blockers). Omit
  this field for aces.

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
- Report only points that ended as an ace or a block: kills (including a kill driven
  through a block touch), attack errors, service errors, and other rally endings are
  not entries.
