# Task: reconstruct every pre-death minimap trajectory

`/workspace/materials/final.mp4` is a continuous segment of Game 5 of the PGL
Wallachia Season 7 Dota 2 grand final between Team Yandex and Team Liquid. Report
every live hero death that belongs to a major teamfight from HUD clock `00:00`
through `50:30`, inclusive.

A major teamfight is a maximal sequence containing at least three hero deaths where
every death after the first occurs less than 15 seconds after the preceding death. A
gap of 15 seconds or more ends the sequence. Do not report isolated deaths or
two-death sequences.

For each death, report the HUD clock, the victim, the roster player credited in the
live kill feed, and the victim's minimap cell at three times: exactly 10 seconds
before the death, exactly 5 seconds before the death, and at the death. `death_cell`
means the victim's final live minimap position immediately before the marker
disappears. A broadcast replay or a kill-feed line that remains on screen is not a
new death.

Use these canonical player labels:

- Team Yandex (Radiant): `watson`, `CHIRA_JUNIOR`, `DM`, `Malady`, `Saksa`
- Team Liquid (Dire): `tOfu`, `Ace`, `Nisha`, `Boxi`, `m1CKe`

Treat the full square minimap as a 14-by-14 grid. Columns `A` through `N` run left
to right (west to east), and rows `1` through `14` run bottom to top (south to
north). `A1` is the Radiant/base corner and `N14` is the Dire/base corner. The cell
containing the center of the victim's minimap marker is the reported cell. If that
center lies exactly on an internal vertical boundary, use the cell to its right
(east); on an internal horizontal boundary, use the cell above it (north). The
outer east and north edges remain in column `N` and row `14`.

Write the events in chronological order to `/workspace/output/solution.json` using
this exact schema:

```json
{
  "events": [
    {
      "game": 5,
      "clock": "12:34",
      "victim": "Nisha",
      "killer": "watson",
      "cell_10s_before": "E7",
      "cell_5s_before": "F7",
      "death_cell": "G8"
    }
  ]
}
```

The object above illustrates the format only. Do not add prose or extra fields.
Use only the supplied video; do not look up the match, video, event logs, or results
online.
