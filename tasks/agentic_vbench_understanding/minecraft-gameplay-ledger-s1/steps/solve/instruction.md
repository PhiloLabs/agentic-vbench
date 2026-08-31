# Minecraft First-Person Gameplay Ledger Reconstruction

You are given one video at `/workspace/materials/game.mp4`: a first-person recording of a
Minecraft session. The player travels across eight biomes (forest, beach, desert, snowy tundra,
jungle, plains, savanna, badlands), gathers many kinds of block, **builds a house block-by-block on camera**,
hunts animals with a **diamond sword** and with a **bow and arrow**, and finally digs a
staircase mine and extracts every ore it exposes.

Reconstruct the player's deliberate action ledger **in the order the actions happen**:

- **mine** — the player breaks a block; report the block type.
- **place** — the player places a block (while building); report the block type.
- **kill** — the player kills a mob; report the mob type **and the weapon used**.

Identify blocks and mobs from their rendered textures. The weapon is visible two ways: the
selected slot in the on-screen hotbar, and how the animal dies — a **sword** kill happens
with the player right next to the animal and swinging, while a **bow** kill happens at a
distance with arrows in flight. Use any tools in the image (for example `ffmpeg` and
`ffprobe`) to seek through and sample the video.

## What to submit

Write `/workspace/output/solution.json`, actions in chronological order:

```json
{
  "events": [
    {"action": "mine",  "target": "oak_log",      "t": 142.5},
    {"action": "kill",  "target": "cow",   "tool": "sword", "t": 210.0},
    {"action": "place", "target": "stone_bricks", "t": 305.2},
    {"action": "kill",  "target": "chicken", "tool": "bow", "t": 480.7},
    {"action": "mine",  "target": "iron_ore",     "t": 12530.0}
  ]
}
```

- `action`: `mine`, `place`, or `kill`.
- `target`: a block type (mine/place) or a mob type (kill), from the vocabulary below.
- `tool`: `sword` or `bow` — required on `kill` events, ignored elsewhere.
- `t`: the time in the **video**, in seconds from the start, at which the action happens (a
  number, e.g. `142.5`; a `mm:ss` / `h:mm:ss` clock string is also accepted). Required on every
  event — it does not have to be exact, within ~10 s is enough (see scoring).

## Vocabulary (closed)

Blocks (mine/place): `oak_log`, `birch_log`, `spruce_log`, `jungle_log`, `acacia_log`,
`dark_oak_log`, `oak_leaves`, `birch_leaves`, `spruce_leaves`, `grass_block`, `dirt`,
`gravel`, `stone`, `cobblestone`, `stone_bricks`, `andesite`, `granite`, `diorite`, `sand`, `sandstone`, `cactus`,
`snow`, `snow_block`, `ice`, `packed_ice`, `red_sand`, `terracotta`, `orange_terracotta`,
`white_terracotta`, `red_terracotta`, `yellow_terracotta`, `brown_terracotta`,
`light_gray_terracotta`, `red_sandstone`, `coarse_dirt`, `podzol`, `clay`, `coal_ore`, `iron_ore`,
`gold_ore`, `redstone_ore`, `diamond_ore`, `lapis_ore`, `emerald_ore`, `oak_planks`,
`spruce_planks`, `birch_planks`, `jungle_planks`, `acacia_planks`, `oak_stairs`, `spruce_stairs`,
`birch_stairs`, `jungle_stairs`, `acacia_stairs`, `oak_fence`, `glass`, `oak_door`, `torch`.

Mobs (kill): `cow`, `pig`, `sheep`, `chicken`, `wolf`, `mooshroom`, `polar_bear`, `turtle`,
`panda`.

## How it is scored

Your events are matched to the ground truth by `(action, target)`, **in order**. A predicted event
can match a true event only if its time `t` is within **±10 seconds** of the true time — you do not
need exact times, but a ledger pinned to the wrong parts of the video will not match.

Reconstruct as much of the ledger as you can, in order: the task is to recover *most* of what
happens across the whole video, not a safe fraction of it, so watch all of it.

**Every target is nameable from the closed vocabulary.** The block and mob **textures are stock
Minecraft** for exactly the named types in the vocabulary above — nothing is retextured or
randomized. Different renders vary *which* named blocks appear (the palette), never how a block
looks, so every on-screen block/mob maps to one vocabulary entry with no legend lookup required.

## Rules
- Stay inside this working directory. Do not read, write, or search outside it.
- Do not look anything up online. Reconstruct the actions from the video, in order.
- Report only `mine`, `place`, and `kill` actions (not walking, looking, or pickups).
