# Block Timeline Reconstruction

You are given one video at `/workspace/frames/ (stills only)`: the full broadcast of a
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

- One entry per block point, in any order.
- `set`: 1 to 4.
- `score_after`: the score right after the point, written `BYU-WashingtonState` —
  the same order the broadcast score graphic displays (BYU on the left).
- `type`: always `"block"` — the point ended at the net off a block (the officially
  scored block point, not a block touch the attacker still kills through, and not a
  deflection that stayed in play). Serve aces, attack errors, and other rally endings
  are not block points and must not be listed.
- `players`: the credited blocker or blockers (one or two names, order does not
  matter). Credit follows the official scorer's rules: a stuff by one player is one
  name; a block shared by two players at the net is two names.
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
- Report only points that ended as a block: kills (including a kill driven through a
  block touch), service aces, attack errors, service errors, and other rally endings
  are not entries.

## Ablation conditions

You have no video and no shell. `./frames/` holds one still every 90 seconds
of the broadcast, named by its timestamp in seconds, and that is everything you
get: you cannot seek, extract more frames, crop, zoom, or run any command. The
only tools available are reading an image and writing a file.

The frames are, in order (open them with the Read tool by path, e.g.
`./frames/00000s.jpg`):

00000s.jpg 00090s.jpg 00180s.jpg 00270s.jpg 00360s.jpg 00450s.jpg 00540s.jpg 
00630s.jpg 00720s.jpg 00810s.jpg 00900s.jpg 00990s.jpg 01080s.jpg 01170s.jpg 
01260s.jpg 01350s.jpg 01440s.jpg 01530s.jpg 01620s.jpg 01710s.jpg 01800s.jpg 
01890s.jpg 01980s.jpg 02070s.jpg 02160s.jpg 02250s.jpg 02340s.jpg 02430s.jpg 
02520s.jpg 02610s.jpg 02700s.jpg 02790s.jpg 02880s.jpg 02970s.jpg 03060s.jpg 
03150s.jpg 03240s.jpg 03330s.jpg 03420s.jpg 03510s.jpg 03600s.jpg 03690s.jpg 
03780s.jpg 03870s.jpg 03960s.jpg 04050s.jpg 04140s.jpg 04230s.jpg 04320s.jpg 
04410s.jpg 04500s.jpg 04590s.jpg 04680s.jpg 04770s.jpg 04860s.jpg 04950s.jpg 
05040s.jpg 05130s.jpg 05220s.jpg 05310s.jpg 05400s.jpg 05490s.jpg 05580s.jpg 
05670s.jpg 05760s.jpg 05850s.jpg 05940s.jpg 06030s.jpg 06120s.jpg 06210s.jpg 
06300s.jpg 06390s.jpg 06480s.jpg 06570s.jpg 06660s.jpg 06750s.jpg 06840s.jpg


Do NOT return an empty list and do NOT refuse. Produce your single best attempt
at output/solution.json from what you can see plus anything you know or can infer
about this match and how a college volleyball match goes. Guess names from the
rosters where you must. A wrong answer is a useful measurement; an empty one is
not. If you cannot open a frame, say so explicitly in your final message.
