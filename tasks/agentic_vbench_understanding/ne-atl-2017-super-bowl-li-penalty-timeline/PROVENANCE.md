# Ground-truth provenance — Super Bowl LI penalty timeline

## Sources
- **Penalty list + game clocks:** official NFL Game Book play-by-play for Super Bowl LI
  (NE 34–28 ATL, 2017-02-05). Cross-checked against nflpenalties.com (13 accepted
  penalties, 88 yards; 16 flags total).
- **Jersey numbers:** the same Game Book's Lineups and Substitutions section (authoritative
  official roster). No jersey number is taken from memory or inference.
- **Independent audio confirmation:** four fouls had their referee-announced number verified
  by transcribing the broadcast audio — #23 R. Alford, #34 B. Poole, #70 J. Matthews,
  #59 D. Campbell. All four matched the official lineup.

## Scope rule (mechanical)
A **scored event** is any penalty in the Game Book play-by-play whose infraction is an
**individual player foul that the referee announces with a jersey number** — whether the
penalty was accepted or declined (the referee announces the number either way). The jersey
number is the player's number in the official Game Book lineup.

## The 13 scored fouls
| # | Q | clock | team | type | player | № | accepted? |
|---|---|-------|------|------|--------|---|-----------|
| 1 | 1 | 13:47 | ATL | offensive holding | P. Worrilow | 55 | yes |
| 2 | 2 | 14:19 | NE | offensive holding | M. Bennett | 88 | declined |
| 3 | 2 | 8:55 | NE | defensive pass interference | P. Chung | 23 | declined |
| 4 | 2 | 8:02 | ATL | defensive holding | R. Alford | 23 | yes (audio ✓) |
| 5 | 2 | 6:10 | ATL | defensive holding | B. Poole | 34 | yes |
| 6 | 2 | 5:16 | ATL | defensive holding | B. Poole | 34 | yes (audio ✓) |
| 7 | 2 | 0:18 | NE | offensive holding | M. Bennett | 88 | yes |
| 8 | 3 | 13:02 | NE | offensive pass interference | C. Hogan | 15 | declined |
| 9 | 3 | 8:43 | NE | defensive pass interference | M. Butler | 21 | yes |
| 10 | 3 | 1:30 | ATL | offensive holding | J. Matthews | 70 | yes (audio ✓) |
| 11 | 4 | 3:50 | ATL | offensive holding | J. Matthews | 70 | yes |
| 12 | 4 | 0:57 | ATL | defensive offside | D. Freeney | 93 | yes |
| 13 | 5 (OT) | 11:18 | ATL | defensive pass interference | D. Campbell | 59 | yes (audio ✓) |

## Exclusions (documented, per maintainer guidance in issue #60)
These Game Book penalties are **not scored** because the referee's announcement does not
carry a player jersey number, by rule/convention:

| Q | clock | team | type | player | № | reason excluded |
|---|-------|------|------|--------|---|-----------------|
| 2 | 8:48 | NE | illegal formation | S. McClellin | 58 | formation foul — announced without a player number |
| 3 | 2:06 | NE | illegal touching (kick) | S. Gostkowski | 3 | kicking-team touching — announced without a player number |
| 3 | 0:04 | ATL | delay of game | M. Bosher | 5 | team foul — no player number |

## Open design questions (for the PR / issue #60)
- **Declined fouls (rows 2, 3, 8):** included here because the referee announces the number.
  If the maintainer prefers accepted-only, dropping them yields 10 events.
- **Event count:** 13 (vs 22 in the NBA worked example). The maintainer suggested widening to
  *every* referee announcement including replay reviews and measurements; those carry no jersey
  number and would need a schema addition, so they are left as a further extension pending
  agreement rather than silently included.
- **Clock precision:** clocks are the official Game Book values; the scorer allows ±5 s. Three
  were additionally confirmed against the on-screen score bug by frame extraction.
