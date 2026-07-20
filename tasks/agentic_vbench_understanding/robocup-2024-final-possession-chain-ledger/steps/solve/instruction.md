# Task: reconstruct the multi-kick possession-chain ledger

The file `/workspace/materials/match.mp4` is a RoboCup Small Size League
robot-soccer match recording covering both halves. Stopped-clock gaps may have been
removed from the recording. The robots with white outer hulls are team `white`; the
robots with black outer hulls are team `black`.

Starting immediately **after the first goal of the match**, reconstruct every
qualifying possession chain in chronological order across the remainder of both
halves. Ignore all play before and including that first goal.

## Definitions

- A **kick** is a distinct robot-ball contact that launches the ball on a new free
  trajectory. Repeated video frames of the same launch count once. Robot movement of
  the ball while play is stopped, including automatic ball placement, does not count.
- A **live-play phase** starts when a kickoff, force start, or direct free kick is
  allowed and ends at the next referee stoppage, goal, or end of half.
- A **possession chain** is a maximal sequence of consecutive kicks by the same hull
  team within one live-play phase. An opponent kick or the end of the live-play phase
  ends the chain.
- Report only **qualifying** chains containing at least two kicks.
- Divide the field length into three equal zones relative to the possessing team's
  direction of attack: `defensive` contains its own goal, `middle` contains midfield,
  and `attacking` contains the opponent goal. `zone_path` is the zone containing the
  ball at each kick point, in order, with consecutive duplicate zone names collapsed.
- `terminal` is `turnover` if the next kick in the same live-play phase is by the
  opponent, `goal` if the chain's team scores before an opponent kick, and `stoppage`
  if live play ends for any other reason before an opponent kick.
- `half` is `1` or `2`. Halftime itself is not a chain.

Do not look up the match, source video, event log, or result online. Derive the ledger
from the supplied video. You may use local video-analysis tools and write intermediate
files under `/workspace/work`.

Write `/workspace/output/solution.json` with exactly this shape:

```json
{
  "chains": [
    {
      "half": 1,
      "team": "white",
      "kick_count": 3,
      "zone_path": ["defensive", "middle", "attacking"],
      "terminal": "turnover"
    }
  ]
}
```

Use only these values:

- `team`: `white`, `black`
- zone: `defensive`, `middle`, `attacking`
- `terminal`: `turnover`, `stoppage`, `goal`

Do not include commentary, confidence scores, timestamps, or unqualified one-kick
chains in `solution.json`.
