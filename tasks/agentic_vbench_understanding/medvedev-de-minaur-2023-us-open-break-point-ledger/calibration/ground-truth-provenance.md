# Ground-Truth Provenance

The official US Open feed for match `1403` reports break-point conversions of
`5/10` for Daniil Medvedev and `2/6` for Alex De Minaur. The 16 opportunity count
is therefore independently fixed before any shot-level annotation is considered.

Point identity, serve direction, rally length, and terminal-stroke fields come from
Match Charting Project record
`20230904-M-US_Open-R16-Daniil_Medvedev-Alex_De_Minaur`. The decoding follows the
`Instructions` sheet in MCP's `MatchChart 0.3.2.xlsm`:

- serves: `4` wide, `5` body, `6` down the T
- groundstrokes: `f` forehand, `b` backhand; slices: `r` forehand, `s` backhand
- volleys: `v` forehand, `z` backhand; other stroke codes retain MCP's documented names
- terminal markers: `*` winner, `#` forced error, `@` unforced error
- court position: volleys, half-volleys, swinging volleys, and smashes default to net;
  other strokes default to baseline; `-` and `=` explicitly override those defaults
- rally shots include the serve and winners but exclude a terminal error stroke

| MCP point | Live serve/rally code | Rally shots | Terminal player | Terminal stroke | Position | Result | Error |
|---:|---|---:|---|---|---|---|---|
| 19 | `6f28f1f3b3y1f-3m3d#` | 7 | Alex De Minaur | backhand_lob | baseline | forced_error | deep |
| 32 | `4+b27h^3b-1*` | 4 | Alex De Minaur | backhand_groundstroke | net | winner | none |
| 42 | `6b29f2n#` | 2 | Daniil Medvedev | forehand_groundstroke | baseline | forced_error | net |
| 65 | `5f28b1f2f2f3b2b3b3b3n@` | 9 | Daniil Medvedev | backhand_groundstroke | baseline | unforced_error | net |
| 66 | `4+b2v3*` | 3 | Alex De Minaur | forehand_volley | net | winner | none |
| 68 | `5b29f3b3b3b3b2b3b3b3b3b3b2f2f2f3s3f3b3b3b3b3b3b2f3*` | 25 | Alex De Minaur | forehand_groundstroke | baseline | winner | none |
| 70 | `5b2d#` | 1 | Daniil Medvedev | backhand_groundstroke | baseline | forced_error | deep |
| 72 | `4*` | 1 | Alex De Minaur | serve | serve | ace | none |
| 108 | `5b38s3b1r2f1r1d#` | 6 | Alex De Minaur | forehand_slice | baseline | forced_error | deep |
| 132 | `4b28f3b3b3b3s1f1f2b3b3b3b3d@` | 12 | Alex De Minaur | backhand_groundstroke | baseline | unforced_error | deep |
| 144 | `4b39f2d@` | 2 | Alex De Minaur | forehand_groundstroke | baseline | unforced_error | deep |
| 166 | `4b28f1f1f3b1f3u1f-1f2b-3*` | 11 | Daniil Medvedev | backhand_groundstroke | net | winner | none |
| 172 | `5b29f1f1u+3i3z1n@` | 6 | Alex De Minaur | backhand_volley | net | unforced_error | net |
| 181 | `5b38b2b2b2b2b+2b1*` | 8 | Daniil Medvedev | backhand_groundstroke | baseline | winner | none |
| 187 | `6#` | 1 | Daniil Medvedev | serve | serve | unreturnable | none |
| 189 | `5f38b1f2f2b1d@` | 5 | Alex De Minaur | backhand_groundstroke | baseline | unforced_error | deep |

For points with a first-serve fault, the table shows the second-serve sequence because
that is the serve which begins the live point. MCP point numbers and raw codes provide
a reproducible audit trail; an independent reviewer should still confirm the visible
stroke classifications against the official match video before task submission.
