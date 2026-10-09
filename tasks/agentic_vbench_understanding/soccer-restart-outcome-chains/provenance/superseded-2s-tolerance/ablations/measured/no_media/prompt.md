# Soccer Match Action Ledger

You are given NO video and NO images, and you have NO tools. The video is the full
broadcast of one Bundesliga match as a single clip, 6426.5 seconds long. Answer from
what you already know. You must still produce a complete answer in the schema below: an
empty sequence is not an acceptable response, so give your best guess.

Time `t` is seconds from the start of the clip. The players' kits, the run of play, the
officials, and the on-screen graphics are your evidence.

## What to submit

Print the JSON object and nothing else as your final message, in exactly this shape:

```json
{
  "sequence": [
    {"t": 2680, "action": "Ball out of play", "team": "none"},
    {"t": 2694, "action": "Throw-in", "team": "home"}
  ]
}
```

One entry per visible action, in chronological order. Fields:

- `t`: the moment of the action, in seconds from the start of the clip. A predicted action
  counts only if its `t` is within 2 seconds of the true moment, so pin each one carefully.
- `action`: exactly one of the seventeen names below, spelled as shown. Each is timed at the
  moment its definition describes.
  - `Ball out of play`: the ball crosses one of the outer lines of the pitch.
  - `Throw-in`: the player throws the ball.
  - `Foul`: the foul is committed.
  - `Direct free-kick`: after a foul, the player strikes the free kick with the intention of
    scoring, or with the defending team lined up in a wall.
  - `Indirect free-kick`: after a foul, the player strikes the free kick with no intention of
    scoring. This is every other free kick, whatever the laws of the game would call it.
  - `Corner`: the player strikes the corner kick.
  - `Penalty`: the player strikes the penalty.
  - `Clearance`: the goalkeeper kicks the ball, as from a goal kick or a punt out of the hands.
    An outfield player's clearance is not this action.
  - `Shots on target`: a player shoots, intending to score, and the ball heads toward the goal
    frame.
  - `Shots off target`: a player shoots, intending to score, and the ball does not head toward
    the goal frame.
  - `Goal`: the ball crosses the goal line.
  - `Kick-off`: at the start of a half or after a goal, the first pass from the centre circle.
  - `Offside`: the assistant referee raises the flag.
  - `Yellow card`: the referee shows a player the yellow card.
  - `Red card`: the referee shows a player a straight red card.
  - `Yellow->red card`: the referee shows a player the red card for a second yellow.
  - `Substitution`: the player being replaced crosses one of the outer lines.
- `team`: the team that performs the action, `"home"` or `"away"`. Home is the team named
  first in the on-screen score graphic; infer the two kits and keep the mapping consistent
  for the whole match. For a foul, an offside or a card, the team is the side of the player
  who commits the foul, is flagged offside or is shown the card. For a goal it is the side
  that scores, for a kick-off the side that kicks off, for a substitution the side making
  it, and for a clearance the goalkeeper's side. `Ball out of play` belongs to neither team:
  give it `"none"`.

## Rules

- Stay inside this working directory. Do not read, write, or search outside it.
- Do not look anything up online, and do not rely on memory of this match; find every
  action in the video.
- Count only actions the live broadcast actually shows. An action that happens off screen
  is not scored, even if a replay shows it later, and a replay never adds a second entry.
