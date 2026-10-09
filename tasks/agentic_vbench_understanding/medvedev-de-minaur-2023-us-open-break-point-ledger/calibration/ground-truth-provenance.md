# Ground-Truth Provenance

The [official US Open full-match broadcast](https://www.youtube.com/watch?v=kYxKCsl4uN0)
for match `1403` reports break-point conversions of `5/10` for Daniil Medvedev and
`2/6` for Alex De Minaur. The official
[match recap](https://www.usopen.org/en_US/news/articles/2023-09-04/best_photos_of_daniil_medvedev_vs_alex_de_minaur_round_4_at_the_2023_us_open.html)
independently identifies the match and 2-6, 6-4, 6-1, 6-2 result. The 16-opportunity
count is fixed before any shot-level annotation is considered.

The current provisional point identity, serve direction, rally length, terminal
fields, and full scored shot sequences come from Match Charting Project record
`20230904-M-US_Open-R16-Daniil_Medvedev-Alex_De_Minaur`. The source is pinned to
MCP commit [`2c59eef194967e688b69e73df344184a06322cd8`](https://github.com/JeffSackmann/tennis_MatchChartingProject/commit/2c59eef194967e688b69e73df344184a06322cd8):

- `charting-m-points-2020s.csv` SHA-256:
  `2cd43f73e0530a47ea4c02b99dae40177ca6d58a8ccf9189358eb05dffb4be9a`
- `MatchChart 0.3.2.xlsm` SHA-256:
  `46e2349eee512296a86170449f6e463a6be91be9261a0c7b6b5d5a25c006729f`

MCP describes the dataset as CC BY-NC-SA 4.0; this file preserves project and
source attribution for the derived labels. MCP is one third-party human annotation;
it is an audit source and does not count as either of this task's required blind
full-video annotations A and B.

The decoding follows the workbook's `Instructions` sheet:

- serves: `4` wide, `5` body, `6` down the T
- groundstrokes: `f` forehand, `b` backhand; slices: `r` forehand, `s` backhand
- volleys: `v` forehand, `z` backhand; other stroke codes retain MCP's documented names
- terminal markers: `*` is a winner after a rally stroke or an ace after the live
  serve; `#` is an unreturnable after the bare live serve or a forced error after a
  return/rally attempt; `@` is an unforced error
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

The 16 live codes expand to 112 ordered shot tokens: 16 serves and 96 later scored
shots. Every later token has an explicit stroke and direction code. Rally
directions decode as `1` = `receiver_forehand`, `2` = `middle`, and `3` =
`receiver_backhand`; both players are right-handed. Per the workbook, these lanes
are the receiver-side 30%, central 40%, and receiver-side 30% of the baseline, based
on where the ball crosses or visibly would have crossed it. The provisional `shots`
oracle keeps exactly those two observable attributes for each token. It does not include
the redundant hitter, which follows from the server and shot-token parity, or MCP's
optional inferred court-position fields.

Nine points end with an error attempt. That attempted shot is present in `shots`
but excluded from `rally_shots`, so `forced_error`, `unforced_error`, and
`error_unknown` points satisfy
`len(shots) == rally_shots + 1`. Winner, ace, and unreturnable points satisfy
`len(shots) == rally_shots`. The 16 sequence lengths are:

```text
8, 4, 3, 10, 3, 25, 2, 1, 7, 13, 3, 11, 7, 8, 1, 6
```

For the six second-serve break points, the pinned MCP first-fault codes are retained
as an audit trail:

| MCP point | First-serve code | Live second-serve code begins |
|---:|---|---|
| 65 | `4n` | `5...` |
| 68 | `6d` | `5...` |
| 144 | `6n` | `4...` |
| 172 | `4n` | `5...` |
| 181 | `c4n` | `5...` |
| 189 | `4n` | `5...` |

For points with a first-serve fault, the table shows the second-serve sequence because
that is the serve which begins the live point. MCP point numbers and raw codes provide
a reproducible audit trail, but MCP's `#` and `@` judgments are annotations rather
than machine truth. They must be checked against the canonical silent video.

MCP point 189 begins at player-specific point score Medvedev `40`, De Minaur `AD`.
An earlier draft inverted those two values; the current oracle and `solve.sh` contain
the corrected identity.

## Observable error criteria

Classify a miss as `forced_error` only when the preceding shot creates immediate,
visible pressure at contact: the hitter is running or stretching, jammed or pulled
outside a normal contact zone, visibly off balance, or denied normal preparation
time. Classify it as `unforced_error` when the hitter reaches a controllable ball in
a neutral position with stable balance, a normal contact zone, and reasonable time
to prepare. Score, player reputation, commentary, and the eventual outcome of the
game are not evidence for this distinction. Use `error_unknown` only when a
non-serve miss is visible but the broadcast does not establish enough of the
preceding pressure, preparation, or contact to make that distinction.

The remaining terminal-result vocabulary is adjudicated as follows:

- `winner`: a non-serve shot lands legally and the opponent makes no subsequent
  racket contact;
- `ace`: a legal serve ends the point without touching the receiver's racket;
- `unreturnable`: the serve touches the receiver's racket but produces no separately
  identifiable return attempt. If an identifiable
  return attempt exists, a miss is classified as `forced_error`, `unforced_error`,
  or `error_unknown` according to the visible pressure evidence instead.

This priority is material for the oracle. MCP point 70 (`5b2d#`) includes an explicit
backhand return directed through the middle and missed deep, so it is a receiver
`forced_error` and its error attempt is a shot token. MCP point 187 (`6#`) has no
separate return token, so it is an `unreturnable` serve with only the serve token.

For a terminal error, `net`, `wide`, `deep`, and `wide_and_deep` describe the visible
miss location. A visibly framed or severe mishit takes priority and is `shank`;
otherwise use the net or landing-location category. `unknown` is used only when the
broadcast does not show the miss location clearly.

For a non-serve terminal shot or error attempt, use `terminal_court_position:
unknown` only when the broadcast does not establish whether the terminal hitter is
behind the service line (`baseline`) or at or inside it (`net`). Ace and
unreturnable terminals always use `serve`. The provisional MCP-derived oracle contains no
`error_unknown` result or unknown court position, but either value remains available
to the independent annotators when the canonical video cannot support a narrower
label.

## Independent annotation and adjudication

The target `human-verified` tier is not yet achieved. Annotators A and B must each
scan the complete 119-minute exact silent artifact end to end, independently discover
every break-point opportunity, and only then annotate the points they found. They
must not see pre-cut point windows, MCP codes, the oracle, or each other's labels.
Each must record every scalar field, the full ordered `shots` array, and a video time
window. Exact agreement is checked field by field and shot token by shot token.

Every disagreement is then reviewed at normal speed and at no faster than 0.5x by a
third adjudicator. The record must preserve both original labels, the final label,
and a short observable rationale. If the video still does not establish a defensible
single value, use the schema's explicit `unknown` value where one exists. Otherwise
that field must be masked from scoring or represented by documented accepted
alternatives; it must not be resolved silently. The required ledger and sign-off
fields are in `independent-annotation.md`.
