# CS2 Trade-Episode Reconstruction

You are given ten videos at `/workspace/materials/P1.mp4` through
`/workspace/materials/P10.mp4`. They are ten time-aligned first-person recordings
of the same full Counter-Strike 2 competitive match on de_cache: `P<k>.mp4` is the
first-person view of player `P<k>`, for the entire match. All ten videos start at
the same instant and share one clock, so a timestamp means the same moment in every
video. Players `P1`-`P5` are one team and `P6`-`P10` the other; the teams swap
sides at halftime (after round 12). The HUD is not rendered: there is no killfeed,
scoreboard, minimap, round timer, or ammo counter.

Reconstruct every **trade episode** in the match.

A **trade episode** is a pair of kills:

1. an **initial kill**: player A kills player B at time `t1`;
2. a **trade kill**: within 5.0 seconds after `t1`, in the same round, a
   **teammate of B** kills A.

If more than one teammate-of-B kills A within the window, the trade kill is the
**earliest** one. Each initial kill produces at most one trade episode. A kill
that is never avenged this way is not part of any episode and must not be reported.

Definitions (these are exactly what is scored):

- A **kill** is the death of a player caused by another player, with any weapon
  including grenades. Deaths from falling or the bomb are not kills.
- **`t`** for each kill: its time in seconds from the start of the videos. Your
  value may differ from the true moment by up to 2 seconds.
- **`round`**: rounds are numbered from 1 in order of play. Both kills of an
  episode are in the same round; a kill in the short aftermath after a round has
  been decided still belongs to that round.
- **`weapon`** for each kill: the weapon that caused it, from this closed
  vocabulary (any capitalization/spacing; matched case- and punctuation-insensitive):
  `AK-47`, `AWP`, `Desert Eagle`, `Five-SeveN`, `Galil AR`, `Glock-18`, `M4A1`
  (the silenced M4A1-S), `M4A4`, `MP9`, `MAC-10`, `PP-Bizon`, `SG 553`, `SSG 08`,
  `UMP-45`, `USP-S`, `HE Grenade`. For a kill this is the weapon the killer used,
  visible as their viewmodel in the killer's own POV.

To reconstruct an episode you generally have to correlate three players' videos:
the initial killer's POV (shows kill 1), the initial victim's POV (confirms who
died and when), and the trader's POV (shows kill 2). Each player's own video shows
their own kills clearly and shows the moment of their own death; after a player
dies, their video is not their own view until the next round, so do not read kills
from a dead player's video. The game audio is real and can help you locate
firefights.

Use any tools available (for example `ffmpeg` and `ffprobe`) to seek through and
sample the videos. The events are spread across the entire ~32-minute match.

## What to submit

Write `/workspace/output/solution.json` in exactly this shape:

```json
{
  "trade_episodes": [
    {
      "round": 6,
      "initial_kill": {"t": 410.5, "killer": "P8", "victim": "P2", "weapon": "AK-47"},
      "trade_kill":   {"t": 413.1, "killer": "P4", "victim": "P8", "weapon": "M4A1"}
    }
  ]
}
```

The entry above is a made-up value illustrating the shape only.

- One entry per trade episode, in any order.
- `initial_kill` / `trade_kill`: each has `t` (number), `killer`, `victim` (labels
  `P1`-`P10`), and `weapon` (one string from the vocabulary).
- `round`: integer, starting at 1.
- In every episode, `trade_kill.victim` must equal `initial_kill.killer` (the
  trade avenges the initial victim by killing the initial killer).

## Rules

- Stay inside this working directory. Do not read, write, or search outside it.
- Do not look anything up online; this match has no public record. Find every
  trade episode in the videos.
- Report only trade episodes as defined above. Do not report ordinary
  (non-traded) kills.
