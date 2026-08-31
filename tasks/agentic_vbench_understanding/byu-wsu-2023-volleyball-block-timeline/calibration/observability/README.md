# Observability ledger

Two questions, answered separately from the shipped 720p video and independently of any
agent output:

1. **When is each point awarded?** — `flips.json` / `flips.md`, all 18 confirmed.
2. **Can the setter be seen?** — `setter-chain.md`, with the rally-window strips in
   `witness/`.

## When each point is awarded

The broadcast carries a centred score bug, `[BYU] 8 BYU | 13 WSU [WSU]`. A 20 s pass
builds a score-versus-time curve; each target score is then pinned to the second and
the bug re-read there to confirm it shows exactly that score. **All 18 confirm**, and
`flips.json` records the read-back per event.

Two properties of this file shaped the method, and both cost a pass to discover:

- **it opens on the end of a different match.** The first minutes are Towson at
  Washington State, with its own score bug reading 21-24 and MATCH POINT. The BYU match
  starts at the first 0-0, near t=340 s.
- **the bug's SET SCORE row is too small to OCR reliably.** Read across the whole match
  it produces impossible values, including a fifth set in a four-set match. Sets are
  therefore bounded by where each set's own scores appear on the curve, not by reading
  that row.

## What the broadcast shows, and when

The score graphic lags the whistle by roughly 5-6 s on this broadcast, and the cut to a
close-up is not at a fixed offset from either: on set 1 at 18-14 it lands after the
graphic has flipped, on set 2 at 10-11 before. An observability pass that assumes one
offset will miss half the events; the strips here span the rally window, and reading the
terminal attribution per event needs a sweep either side of the flip.

`witness/<event>_rally.jpg` holds four frames from the rally window of each point
(t-9, -7, -5, -3 relative to the flip), at the source's horizontal resolution. They are
the evidence for the setter finding: that window is the wide sideline shot throughout,
where numbers do not resolve.
