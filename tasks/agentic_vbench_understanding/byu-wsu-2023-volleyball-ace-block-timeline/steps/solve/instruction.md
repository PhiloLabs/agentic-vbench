# Block Timeline Reconstruction

You are given one video at `/workspace/materials/match.mp4`: the full broadcast of a
college women's volleyball match (BYU at Washington State, four sets). The video has
no audio track. Find every point in the match that ended as a **block**, by either
team.

For each block point, report the set, the score immediately after the point, the
player(s) credited with the block, the opposing hitter who was blocked, and the
setter who fed that attack. Use any tools in the image (for
example `ffmpeg` and `ffprobe`) to seek through and sample the video. The on-screen
score graphic, the players' jersey numbers, and the play action are your evidence.
The rosters below map jersey numbers to names.

## What to submit

Write `/workspace/output/solution.json` in exactly this shape:

```json
{
  "events": [
    {"set": 2, "score_after": "7-12", "type": "block", "players": ["First Last", "First Last"], "blocked": "First Last", "setter": "First Last"},
    {"set": 4, "score_after": "20-16", "type": "block", "players": ["First Last"], "blocked": "First Last", "setter": "First Last"}
  ]
}
```

- One entry per qualifying point, in any order.
- `set`: 1 to 4.
- `type`: always `"block"`.
- `score_after`: the score right after the point, written `BYU-WashingtonState` —
  the same order the broadcast score graphic displays (BYU on the left).
- `type`: `"ace"` — the serve scored directly (untouched, or unplayable off the
  receiver); `"block"` — the point ended at the net off a block (the officially
  scored block point, not a deflection that stayed in play).
- `players`: for an ace, the server (one name). For a block, the credited blocker or
  blockers (one or two names, order does not matter). Credit follows the official
  scorer's rules: a stuff by one player is one name; a block shared by two players
  at the net is two names.
- `blocked`: the opposing hitter who was blocked — the player whose attack the block
  stopped (one name, on the team opposite the blockers).
- `setter`: the player who set that attack — the team-mate who delivered the ball to
  the blocked hitter earlier in the same rally (one name, same team as `blocked`).

## Rosters (jersey number → name)

BYU (shown left on the score graphic):

| # | Name | | # | Name |
|---|---|---|---|---|
| 1 | Kate Prior | | 12 | Claire Little |
| 4 | Hannah Billeter | | 13 | Mia Lee |
| 7 | Whitney Bower | | 14 | Aria McComber |
| 8 | Eden Bower | | 15 | Elyse Stowell |
| 9 | Alyssa Erickson | | 18 | Kamaile Hiapo |
| 10 | Erin Livingston | | 21 | Whitney McEwan-Llarenas |
| | | | 24 | Brielle Kemavor |

Washington State (shown right on the score graphic):

| # | Name | | # | Name |
|---|---|---|---|---|
| 3 | Karly Basham | | 12 | Argentina Ung |
| 5 | Iman Isanovic | | 13 | Emma Barbero |
| 7 | Pia Timmer | | 15 | Magda Jehlarova |
| 8 | Katy Ryan | | 21 | Lana Radakovic |
| 11 | Julia Norville | | |

## Rules

- Stay inside this working directory. Do not read, write, or search outside it.
- Do not look anything up online, and do not rely on memory of this match; find every
  qualifying point in the video.
- Report only points that ended as an ace or a block: kills, attack errors, service
  errors, and other rally endings are not entries.
