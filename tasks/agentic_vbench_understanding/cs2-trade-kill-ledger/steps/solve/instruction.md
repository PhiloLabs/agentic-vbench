# CS2 Trade-Kill Ledger

You are given ten videos at `/workspace/materials/P1.mp4` through `/workspace/materials/P10.mp4`.
They are ten time-aligned first-person recordings of the same full Counter-Strike 2
competitive match on de_cache: `P<k>.mp4` is the first-person view of player `P<k>`,
for the entire match. All ten videos start at the same instant and share one clock,
so a timestamp means the same moment in every video. Players `P1`-`P5` are one team
and `P6`-`P10` the other; the teams swap sides at halftime. The HUD is not rendered:
there is no killfeed, scoreboard, minimap, or round timer.

Reconstruct the complete kill ledger of the match: every kill, in chronological
order, with who killed whom, when, in which round, and whether the kill was traded.

Definitions (these are exactly what is scored):

- A **kill** is the death of a player caused by another player, with any weapon
  including grenades. Deaths from falling, the exploding bomb, or other world damage
  are not kills and must not be listed.
- **`t`**: the time of the kill in seconds from the start of the videos. Your value
  may differ from the true moment by up to 5 seconds.
- **`round`**: rounds are numbered from 1 in order of play. A kill in the short
  aftermath after a round has been decided still belongs to that round.
- **`was_traded`**: `true` if and only if the killer is themselves killed within
  5.0 seconds, in the same round, by any player on the victim's team - including
  the victim themselves, e.g. by a grenade they threw before dying. Trades never
  carry across a round boundary.
- **`trader`**: the player who killed the killer within that window, or `null` if
  `was_traded` is `false`.

Use any tools in the image (for example `ffmpeg` and `ffprobe`) to seek through and
sample the videos. The victim's own video always shows their death. Most kills are
also visible in the killer's video; for a grenade kill, the killer's video shows the
throw, not necessarily the impact. After a player dies, their video may show other
players' views until the next round begins; only footage from while a player is
alive is that player's own view.

## What to submit

Write `/workspace/output/solution.json` in exactly this shape:

```json
{
  "ledger": [
    {"t": 21.2,  "round": 1, "victim": "P2", "killer": "P7", "was_traded": false, "trader": null},
    {"t": 191.3, "round": 3, "victim": "P8", "killer": "P3", "was_traded": true,  "trader": "P4"}
  ]
}
```

- One entry per kill, in any order.
- `t`: seconds from the start of the videos, as a number.
- `victim`, `killer`, `trader`: player labels `P1`-`P10` (`trader` may be `null`).
- `round`: integer, starting at 1.
- `was_traded`: JSON boolean.

## Rules

- Stay inside this working directory. Do not read, write, or search outside it.
- Do not look anything up online; this match has no public record. Find every kill
  in the videos.
- List every kill by either team, and only kills as defined above.
