# Task: reconstruct the scoring ledger of a lacrosse game

You are given one silent video: `game.mp4` — the full broadcast of one men's
field-lacrosse game (four quarters). The on-screen scoreboard/graphic has been
blacked out, and there is no audio. You must reconstruct what happened from the
play on the field alone.

There are two teams, distinguished by jersey color:
- **NAVY** — dark navy-blue jerseys (numbers in yellow/maize).
- **WHITE** — white jerseys (numbers in light blue).

A closed list of the valid jersey numbers for each team is in `roster.json`
(numbers only — no names are needed or provided). Every number you output must
be a number a player actually wears on that team.

## What to produce

Write `output/solution.json` with two ordered lists.

### 1. `goals` — every goal, in the order they were scored
For each goal:
- `team`: `"NAVY"` or `"WHITE"` — the team that scored.
- `scorer`: the jersey number of the player who scored (integer).
- `assister`: the jersey number of the teammate who threw the pass that led
  directly to the goal, or `null` if the goal was unassisted (the scorer
  created it himself with no immediate assisting pass).

List the goals in chronological order. There is no need to report a clock time.

### 2. `penalties` — every penalty, in order
For each penalty:
- `team`: `"NAVY"` or `"WHITE"` — the penalized team.
- `offender`: the jersey number of the penalized player, or `null` if it is a
  team penalty with no single player (e.g. a face-off violation or offside on
  the unit).
- `type`: a short lowercase string, one of: `"pushing"`, `"slashing"`,
  `"cross-check"`, `"holding"`, `"unnecessary roughness"`, `"offside"`,
  `"faceoff violation"`, `"illegal body check"`, `"tripping"`,
  `"illegal procedure"`, `"other"`.

## Output format

```json
{
  "goals": [
    {"team": "NAVY", "scorer": 89, "assister": null},
    {"team": "WHITE", "scorer": 51, "assister": null},
    {"team": "NAVY", "scorer": 2, "assister": 40}
  ],
  "penalties": [
    {"team": "NAVY", "offender": 5, "type": "pushing"}
  ]
}
```

## Notes
- A goal counts when the ball fully crosses the goal line into the net in live
  play (the scoring team celebrates and possession resets to the other team's
  goalie via a whistle/restart). Do not count shots that are saved, hit the
  post, or are waved off.
- Jersey numbers repeat across the two teams (both teams may have a player
  wearing the same number), so always pair the number with the correct team
  color.
- The goal ledger is graded as a full ordered reconstruction: each goal is
  checked on its team, its scorer, whether it was assisted (assister non-null
  vs null), AND the running score after it (the cumulative NAVY-WHITE tally,
  derived from your ordered list). So finding every goal, in the correct order,
  attributed to the correct team, matters as much as reading the scorer — a
  missed, extra, or mis-teamed goal shifts the running score for every goal
  after it. Be exhaustive and get the sequence right. The specific assister
  number and the penalties are recorded as diagnostics and do not affect the
  goal score.
