# Task

`materials/frame.jpg` is one frame taken from a thirty-minute recording of a
camera moving over a voxel sandbox world. The camera did exactly two things to
that world, and nothing else in it ever changed:

- **place** — a new block appeared on top of the terrain, always one of the six
  types listed below.
- **remove** — a block the camera had placed earlier in the same recording
  disappeared.

No part of the original terrain was ever removed, and the camera never placed a
block on top of another block it had placed.

At each of the thirty times below, report **how many camera-placed blocks of
each type are standing** at that moment. Do not write any file. Give the result as
a single JSON object at the end of your reply.

The times, in seconds from the first frame of the video:

```
  60   120   180   240   300   360   420   480   540   600
 660   720   780   840   900   960  1020  1080  1140  1200
1260  1320  1380  1440  1500  1560  1620  1680  1740  1800
```

## Output format

```json
{
  "census": {
    "60":  {"birchwood": 7, "bookshelf": 1, "brick_block": 4,
            "gravel": 2, "hardened_clay_orange": 0, "mossycobble": 3},
    "120": {"birchwood": 12, "bookshelf": 2, "brick_block": 9,
            "gravel": 5, "hardened_clay_orange": 1, "mossycobble": 6}
  }
}
```

One entry per time, keyed by the time in seconds exactly as written above.
Each entry gives an integer count for every one of the six types; use `0` for
a type with none standing. A count scores only when it is exactly right.

## The six block types

| name | what it looks like |
|---|---|
| `birchwood` | pale, almost white planks |
| `bookshelf` | brown frame with coloured book spines |
| `brick_block` | red brick |
| `gravel` | speckled grey and brown |
| `hardened_clay_orange` | flat orange |
| `mossycobble` | grey cobblestone with green moss |

Nothing is retextured; these are the game's stock textures. No other type of
block is ever placed.

## Rules

- Stay inside this working directory.
- Do not look anything up online. Work the counts out from the video.

## Rules

- Run no commands and use no tools. Answer from the attached frame alone.
- You must give an integer for every one of the 180 counts. Declining, or
  returning null, or returning an error, is not an acceptable answer. Where you
  are unsure, give your best estimate. A wrong estimate is worth more here than
  no answer.
