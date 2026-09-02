# Tennis Rally-Stroke Ledger Task

You are given:

- `/workspace/materials/match.mp4`: one continuous broadcast of a women's singles
  tennis final between **Serena Williams** and **Maria Sharapova**. 1280x720, **25
  frames per second**, 123875 frames, with an audio track.
- `/workspace/materials/vocabulary.json`: the complete closed label space — every
  player and every stroke class you are allowed to use.

Reconstruct the complete chronological ledger of every **rally stroke** played in the
match: who hit it, whether it was a forehand or a backhand, and the frame on which the
stroke begins. Frame numbers follow the video's 25 fps and **the first frame of the
video is frame 0**, so frame `n` is at time `n / 25` seconds.

The broadcast opens with several minutes of walk-on and warm-up before the first point;
warm-up strokes are not part of the match and are not scored.

## What counts as one rally stroke

A rally stroke is one swing by one player at the ball during a live point — every shot
except the serve.

- **Serves are not rally strokes and must not appear in your ledger.** The serve is the
  shot the server plays to start the point, standing behind her own baseline and hitting
  the ball out of her own toss. Every other shot in the point is a rally stroke,
  **including the return of serve**, which is the first rally stroke of the point.
- Report every stroke a player actually swings at, including the shot that ends the
  point — a winner, or a ball hit into the net or long. If a player swings and misses
  the ball completely, or lets the ball go by without swinging, that is not a stroke.
- Players strike alternately within a point, so two consecutive entries in your ledger
  are normally by different players. The gap between one stroke's start frame and the
  next inside a rally is typically 25 to 40 frames.
- Long stretches of the video contain no rally strokes at all — serves and aces,
  changeovers, replays, celebrations, and the gaps between points. Broadcast replays
  repeat strokes you have already logged; log each stroke once, at the frame where it
  happens in live play, not where the replay shows it.

### Where a stroke begins

`start_frame` is the first frame of the **take-back**: the frame on which the player's
shoulders turn and the racquet begins to move back for that swing. This is roughly 10
frames before the racquet strikes the ball, so it is normally under way while the
incoming ball is still crossing the net.

Two things this is **not**:

- It is not the moment of racquet–ball contact. Contact is the obvious moment — it is
  what you hear on the audio track and what a sampled frame shows — but it is about 10
  frames too late.
- It is not the moment the player starts running toward the ball. A player often chases
  a ball for half a second with the racquet still in front of her; the take-back is when
  the racquet itself starts going back.

`start_frame` must be within **8 frames (0.32 seconds)** of the true frame for the
stroke to be counted, so pin each one carefully rather than estimating. Sampling one
frame every half second is not enough to place a stroke this tightly; step frame by
frame around each swing.

## Vocabulary

`player` is who struck the ball, spelled exactly as in `vocabulary.json`. The 2 players
are:

`Sharapova`, `Williams`

`stroke` is the stroke class, spelled exactly as in `vocabulary.json`. The 2 classes
are:

`backhand`, `forehand`

Notes on how the vocabulary is applied:

- `forehand` / `backhand` classify the stroke by which side of the body the player takes
  it on. Use the player's own handedness, not the side of the screen: both of these
  players are right-handed, so a stroke taken on their right side is a `forehand` and
  one taken on their left side is a `backhand`.
- Every rally stroke is one or the other. Overheads, smashes, volleys, drop shots,
  slices and lobs are all still just `forehand` or `backhand`; there is no separate class
  for them, and a return of serve is an ordinary `forehand` or `backhand`.

Identifying the player is part of the task. The camera stays behind one baseline for the
whole match, so the players trade near and far ends as the match goes on; tell them apart
by their appearance and kit rather than by which half of the frame they are in.

## What to submit

Write `/workspace/output/solution.json` in exactly this shape:

```json
{
  "strokes": [
    {"player": "Sharapova", "stroke": "backhand", "start_frame": 41135},
    {"player": "Williams", "stroke": "forehand", "start_frame": 41168},
    {"player": "Sharapova", "stroke": "forehand", "start_frame": 41199}
  ]
}
```

Requirements:

- `player`: one player from the vocabulary above.
- `stroke`: one stroke class from the vocabulary above.
- `start_frame`: an integer frame number in `[0, 123874]`.
- Entries must be ordered by non-decreasing `start_frame`.

Use `ffmpeg` and `ffprobe` (both installed) to seek through and sample the video. To
extract exactly frame `n`, select on the frame index rather than by timestamp, for
example:

```bash
ffmpeg -v error -i /workspace/materials/match.mp4 \
       -vf "select=between(n\,30770\,30830)" -vsync 0 /workspace/work/f_%05d.png
```

The audio track is part of the material: racquet strikes produce audible transients,
which makes audio a cheap way to find candidate strokes in a long video — remember
that the take-back you are asked to report comes about 10 frames before the sound.

## Rules

- Stay inside this working directory. Do not read, write, or search outside it.
- Do not look anything up online, and do not rely on any memory of this match, these
  players, or this dataset; every stroke must come from watching and listening to the
  video.
