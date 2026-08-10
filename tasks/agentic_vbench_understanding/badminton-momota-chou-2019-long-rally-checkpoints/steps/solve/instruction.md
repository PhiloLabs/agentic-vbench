# Full-match badminton long-rally checkpoint reconstruction

Analyze the complete broadcast at `/workspace/materials/game.mp4`. Find every
live-play singles rally containing at least 20 strokes, then reconstruct three
checkpoint states for each qualifying rally.

Use local tools such as FFmpeg, ffprobe, scripts, and frame extraction. Inspect the
full video. Do not use the Internet, pre-existing annotations, or files outside
`/workspace`.

## Definitions

- A **stroke** is a racket contact that sends the shuttle toward the opponent.
  Count the serve as stroke 1. Do not count warm-ups, replays, dead-ball swings,
  or duplicate broadcast angles.
- A **rally** starts at the serve contact and ends at the last racket contact
  before the point is awarded.
- A rally qualifies when `stroke_count >= 20`.
- `rally_start_s` and `contact_s` are seconds from the first video frame.
- Use set values `1`, `2`, or `3`.
- Use player names exactly as `MOMOTA` and `CHOU`.
- For a qualifying rally with `N` strokes, report exactly:
  - `fifth`: stroke 5
  - `midpoint`: stroke `ceil(N / 2)`
  - `final`: stroke `N`

At each checkpoint, record the hitter, the hitter's court zone at contact, the
receiver's court zone at the same moment, and the shuttle destination zone for
that stroke.

## Court-zone convention

Use `/workspace/materials/court-grid.png`. Normalize every half-court from that
player's viewpoint: stand behind the player's baseline and face the net.

- Orient `hitter_zone` from the hitter's viewpoint.
- Orient `receiver_zone` independently from the receiver's viewpoint.
- Orient `destination_zone` from the receiving player's viewpoint.
- Player-location zones are `1..9`.
- Shuttle destinations may be inside (`1..9`) or outside (`10..16`).
- If a player's feet straddle a boundary, use the zone containing the midpoint
  between the feet.
- If the shuttle lands on a boundary, use the zone containing most of the shuttle
  cork at first floor contact.

The normalized grid is:

```text
                         NET
             left out             right out
                 10   |  2 | 7 | 1  |   16
                 11   |  6 | 8 | 5  |   15
                 12   |  4 | 9 | 3  |   14
                      +------------+
                         BASELINE
                  13 = behind the baseline
```

## Required output

Write valid JSON to `/workspace/output/solution.json`:

```json
{
  "rallies": [
    {
      "set": 1,
      "rally_start_s": 0.0,
      "stroke_count": 20,
      "rally_winner": "MOMOTA",
      "checkpoints": [
        {
          "kind": "fifth",
          "stroke_index": 5,
          "contact_s": 0.0,
          "hitter": "MOMOTA",
          "hitter_zone": 1,
          "receiver_zone": 2,
          "destination_zone": 3
        },
        {
          "kind": "midpoint",
          "stroke_index": 10,
          "contact_s": 0.0,
          "hitter": "CHOU",
          "hitter_zone": 4,
          "receiver_zone": 5,
          "destination_zone": 6
        },
        {
          "kind": "final",
          "stroke_index": 20,
          "contact_s": 0.0,
          "hitter": "CHOU",
          "hitter_zone": 7,
          "receiver_zone": 8,
          "destination_zone": 9
        }
      ]
    }
  ]
}
```

Include every qualifying rally and no non-qualifying rally. Each rally must contain
one `fifth`, one `midpoint`, and one `final` checkpoint. Do not add prose to the
JSON file. Rally starts have a 2-second tolerance and checkpoint contacts have a
1-second tolerance; categorical values and stroke counts are exact.
