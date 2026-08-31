# Task: build the Melee combo-and-kill causal ledger

The file `/workspace/materials/match.mp4` contains ten complete Super Smash Bros.
Melee games from three Nouns Bowl 2025 sets, concatenated in this order:

| global game | set | players |
|---:|---|---|
| 1-3 | Ferriswheel vs Zain | Ferriswheel, Zain |
| 4-6 | JoJo vs Bard | JoJo, Bard |
| 7-10 | Axe vs SRM13 | Axe, SRM13 |

Reconstruct every qualifying conversion in chronological order. A conversion is one
player's continuous punish sequence against the other player.

## Operational definitions

- A conversion starts when a hit or grab puts a player into damage, capture, or
  command-grab state.
- It remains the same conversion across subsequent hits and grabs. It ends on stock
  loss, or after the victim has been in an actionable grounded state for **more than
  45 consecutive frames** without being damaged or grabbed again.
- `hit_count` is the number of damage-producing contacts in the conversion. Count
  each pummel and each damaging part of a multi-hit move. A throw that deals damage
  counts as a hit.
- Report a conversion if `hit_count >= 4`, **or** if it kills at any hit count.
- `victim_stock_before` is the victim's stock count when the conversion starts.
- Sum the damage added by the conversion and assign `damage_band`: `light` for less
  than 25%, `heavy` for 25% to less than 50%, and `devastating` for at least 50%.
- `terminal` is `kill` when the victim loses a stock. It is `reversal` when the
  victim starts an overlapping conversion against the original attacker before the
  original conversion's 45-frame reset completes. Otherwise it is `escape`.
- Trades can produce overlapping conversions. Record each qualifying conversion at
  its own start position in the ledger.
- Ignore unfinished, non-kill conversions cut off by the end of a game.

Do not look up the sets, replay files, statistics, or results online. Derive the
ledger from the supplied video. You may use local video-analysis tools and write
intermediate files under `/workspace/work`.

Write `/workspace/output/solution.json` with exactly this shape:

```json
{
  "events": [
    {
      "game": 1,
      "attacker": "Zain",
      "victim_stock_before": 4,
      "hit_count": 6,
      "damage_band": "heavy",
      "terminal": "escape"
    }
  ]
}
```

Use only player tags shown in the table, global game numbers `1` through `10`,
`damage_band` values `light`, `heavy`, `devastating`, and `terminal` values `escape`,
`reversal`, `kill`. Do not include timestamps, move names, commentary, confidence
scores, or non-qualifying conversions.
