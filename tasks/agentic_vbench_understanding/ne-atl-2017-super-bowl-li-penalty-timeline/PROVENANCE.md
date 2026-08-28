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

## Clock rule (observable, mirrors `steps/solve/instruction.md`)
`clock` is the game clock shown in the on-screen score bug on the **last frame it is
displayed before the referee begins the foul announcement** — not the time the play
ended, not the down-and-distance display, not any other frame. The score bug is hidden
during live action and restored between plays, so this rule names one unambiguous frame
rather than leaving the agent (or the ground-truth author) to choose among several
plausible displayed times. **Audit status: defined, not yet audited against broadcast
frames per row.** Three rows (see table) were spot-checked against the score bug by
frame extraction during initial design; the full per-row audit against this exact rule
— including a normal accepted foul, a declined foul, and the OT case — is open, per
issue #60 review ask #5.

## The 13 scored fouls
| # | Q | clock | team | type | player | № | accepted? | audio-verified? |
|---|---|-------|------|------|--------|---|-----------|------------------|
| 1 | 1 | 13:47 | ATL | offensive holding | P. Worrilow | 55 | yes | PENDING |
| 2 | 2 | 14:19 | NE | offensive holding | M. Bennett | 88 | declined | PENDING |
| 3 | 2 | 8:55 | NE | defensive pass interference | P. Chung | 23 | declined | PENDING |
| 4 | 2 | 8:02 | ATL | defensive holding | R. Alford | 23 | yes | ✓ |
| 5 | 2 | 6:10 | ATL | defensive holding | B. Poole | 34 | yes | PENDING |
| 6 | 2 | 5:16 | ATL | defensive holding | B. Poole | 34 | yes | ✓ |
| 7 | 2 | 0:18 | NE | offensive holding | M. Bennett | 88 | yes | PENDING |
| 8 | 3 | 13:02 | NE | offensive pass interference | C. Hogan | 15 | declined | PENDING |
| 9 | 3 | 8:43 | NE | defensive pass interference | M. Butler | 21 | yes | PENDING |
| 10 | 3 | 1:30 | ATL | offensive holding | J. Matthews | 70 | yes | ✓ |
| 11 | 4 | 3:50 | ATL | offensive holding | J. Matthews | 70 | yes | PENDING |
| 12 | 4 | 0:57 | ATL | defensive offside | D. Freeney | 93 | yes | PENDING |
| 13 | 5 (OT) | 11:18 | ATL | defensive pass interference | D. Campbell | 59 | yes | ✓ |

All 4 audio-verified rows so far are **accepted** fouls. Per issue #60 review ask #2,
the 3 **declined** fouls (rows 2, 3, 8) are kept in scope on the rule-based assumption
that the referee announces the number regardless of the ensuing penalty decision — that
assumption is not yet independently confirmed by transcription for these specific three,
and is called out here rather than left implicit.

## Announcement-class enumeration (issue #60 review ask #1)
Cross-checked the Game Book-derived penalty list above against nflpenalties.com's
independent penalty log for this game — the two sources agree on all 16 flags (13
scored + 3 excluded below), which is a second, independent confirmation of the scope
table beyond the original Game Book parse.

| class | count this game | jersey number announced? | on-screen graphic | OCR-shortcut risk |
|---|---|---|---|---|
| player foul (accepted or declined) | 13 | yes (audio only, per SPEC evidence) | type + team banner only | none — number never appears on screen |
| team foul (delay of game, illegal formation, illegal touching) | 3 | no | type + team banner only | n/a — correctly excluded, no number to leak or guess |
| replay review | ≥1 (Q4, Falcons challenge of the Edelman catch, upheld) | no — not a foul, no jersey number or infraction type in this schema | on-screen "under review" / ruling graphic | out of scope for this schema; would need new fields, not a drop-in addition |
| measurement | none found | no | chain-gang graphic | none found this game |

**Status: partial.** The player-foul and team-foul rows are corroborated by two
independent sources (Game Book parse + nflpenalties.com) and match exactly. The replay
row is from general web sources, not yet cross-checked against the Game Book or the
broadcast directly, and no measurement was found in either source — both should be
confirmed against the primary Game Book PDF before this table is treated as final.
Reviews and measurements do not carry a jersey number in this game's broadcast, so
adding them to reach the ≥20-event target from review ask #4 would either require
inapplicable/nullable fields on every row or dilute the audio/video seam the task is
built around (they're visible on-screen, no audio-only component) — see the response to
issue #60 for the scope/scoring recommendation.

## Exclusions (documented, per maintainer guidance in issue #60)
These Game Book penalties are **not scored** because the referee's announcement does not
carry a player jersey number, by rule/convention:

| Q | clock | team | type | player | № | reason excluded |
|---|-------|------|------|--------|---|-----------------|
| 2 | 8:48 | NE | illegal formation | S. McClellin | 58 | formation foul — announced without a player number |
| 3 | 2:06 | NE | illegal touching (kick) | S. Gostkowski | 3 | kicking-team touching — announced without a player number |
| 3 | 0:04 | ATL | delay of game | M. Bosher | 5 | team foul — no player number |

## Open design questions (for the PR / issue #60)
- **Declined fouls (rows 2, 3, 8):** included because the scope rule says the referee
  announces the number regardless of the penalty decision. That assumption is verified
  by transcription for 0 of these 3 rows so far (see the audio-verified column above) —
  still open until confirmed the same way the 4 accepted rows were.
- **Event count:** 13 natural events (16 total referee-mic penalty announcements, minus
  3 with no jersey number). Reaching the ≥20 figure from review ask #4 would require
  adding replay reviews and/or measurements, but this game has at most 1 review and no
  measurements (see enumeration table above), and neither carries a jersey number or an
  audio-only component — padding with them would dilute the audio/video seam rather than
  extend it. Recommendation: keep the ~13-event scope and address the F1 fragility
  (review ask #4's "single lucky guess clears 0.10" concern) as a scoring-shape question
  instead of an event-count question.
- **Clock precision:** superseded by the observable clock rule above (per review ask #5)
  — clocks are the official Game Book values, scorer tolerance ±5 s, 3 of 13 rows
  spot-checked against the score bug by frame extraction; full per-row audit against the
  rule is open.
