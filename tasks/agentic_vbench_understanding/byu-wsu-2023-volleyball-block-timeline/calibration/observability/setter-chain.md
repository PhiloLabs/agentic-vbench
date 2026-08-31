# Can the setter be seen?

The scorer asks for three attributions per block point. Two of them — the credited
blockers and the stuffed hitter — are at the net when the rally ends. The third, the
setter who fed that attack, touched the ball several seconds earlier, and this file
answers whether that is recoverable from the shipped video.

## Directly: no

The set happens mid-rally, and mid-rally this broadcast is on the wide sideline camera.
Players are 40-60 px tall there and jersey numbers do not resolve; the frame strips
under `witness/` show the window before each point ending. Nothing in the rally window
yields a readable number, so the setter cannot be read the way a blocker sometimes can.

## By rotation continuity: partly

Volleyball assigns the set to one player at a time, so the field is determined by who
is running the offence rather than by reading a number on the play. Taking the answer
key's own setter assignments across the 18 points:

| team | setters used | events |
|---|---|---|
| BYU | Whitney Bower, and nobody else | 10 of 10 |
| Washington State | Argentina Ung (5) and Karly Basham (3) | 8 |

**On the BYU side the field is fully determined by continuity.** Every BYU attack in the
key is set by Whitney Bower, so an agent that identifies BYU's setter once — from any
close-up where 7 is legible — has the setter for all ten BYU-attacked block points
without reading another number.

**On the Washington State side it is not.** Ung and Basham alternate, and they alternate
*within* set 4 rather than substituting once: Basham at 5250 s, 5526 s and 6514 s, Ung
at 6446 s and 6484 s. Continuity narrows the answer to two names; choosing between them
needs the rotation actually tracked through the set, or the set itself seen.

A structural check on the key, which holds: in all 18 events the setter is on the same
team as the blocked hitter, which is what the official record's `Set by X → Attack by Y
→ Block by Z` chain requires.

## What this means for the task

The setter is the attribution that cannot be shortcut by finding one camera angle. Ten
of eighteen fall out of a single identification plus continuity; the other eight need
the offence tracked. That is the intended shape — the field was added because the
blockers and the hitter can both be read off one post-point close-up, and a third
attribution that cannot be is what stops the timeline layer from carrying the score.
