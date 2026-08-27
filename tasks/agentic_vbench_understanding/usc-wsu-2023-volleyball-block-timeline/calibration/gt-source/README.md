# Ground-truth source snapshot

`pbp_rows_3252428.json` — canonical extract of the official NCAA rally-by-rally log
for this match (stats.ncaa.org contest 3252428, #25 USC at #9 Washington State,
2023-11-12). The site blocks non-browser clients (curl returns 403), so the extract
was captured in a real browser session on 2026-08-27 from
`https://stats.ncaa.org/contests/3252428/play_by_play`: for each of the five per-set
rally tables, every row's `[visitor_cell, score_cell, home_cell]` innerText,
whitespace-normalized. This is the complete rally record the GT derives from —
nothing outside these rows is used.

- sha256 (of the JSON file, computed independently in the capturing browser and
  after transfer): `350308ca11f51ea56e7bd3732d11e3a1145e7f86fdf43b92c159a0c740fc5403`
- row counts per set: 318 / 372 / 336 / 453 / 240

`build_ground_truth.py` — deterministic builder: parses the snapshot and rebuilds
the 23 block points (score-delta decides the scoring team; a scoring row is a block
point iff its rally text ends in `Block by <names>` with an `Attack by <hitter>`
earlier in the chain; `Kill by X, Block by Y` rows are kills through a block touch
and are excluded, exactly matching the box score's Block Solos 3/3 + Block Assists
14/20 -> team blocks 10/13). It prints a per-event source-row mapping and, with
`--judge ../../steps/solve/tests/judge.py`, asserts exact equality with
`GROUND_TRUTH` (verified: 23/23).

Record formats present in this contest's rally tables: terminal blocks appear as
`..., Attack by <hitter>, Block by <name>[, <name>]` (100 `Block by` occurrences
total, including non-terminal touches); no `Attack error by X (block by Y ...)`
row exists in this contest's tables (0 occurrences — checked case-insensitively
across every cell).
