# Task

`/workspace/materials/session.mp4` is an uninterrupted recording of a camera moving over a
voxel sandbox world. The camera does exactly two things to that world, and
nothing else in it ever changes:

- **place** — a new block appears on top of the terrain. It is always one of
  the six types listed below.
- **remove** — a block that the camera placed earlier in this same recording
  disappears.

No part of the original terrain is ever removed, and the camera never places a
block on top of another block it placed. So at any moment there is a definite
set of camera-placed blocks standing in the world: every one it has placed,
minus every one it has since removed.

At each of the thirty times below, report **how many camera-placed blocks of
each type are standing** at that moment. Write the result to
`/workspace/output/solution.json`.

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
