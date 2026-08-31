# Mob-render audit — prismarine-viewer 1.33, Minecraft 1.16.5 (2026-07-22)

**Why this audit exists.** The task asks an agent to name the mob in each `kill` event from
the video alone. If the renderer does not draw a mob, that ground-truth event is
unanswerable and the task is unfair — the benchmark would be grading a coin flip. So every
mob in the task vocabulary must be *seen* to render before it is allowed into the ledger.

**Method.** `audit_mobs.js` + `audit_mobs.py`. The bot stands on a clean stone platform
built at its own column (a `/fill` in an unloaded chunk silently fails), summons one mob
3 blocks ahead, and **tracks it with the camera** the way a player does while fighting it.
The capture side is marker-driven, not timer-driven: the bot writes the mob name to a file
once the mob is framed, the capture screenshots and then clears the file to release the
bot. This removes the drift that made a first, time-scheduled pass mislabel every shot.
Both a free-camera pass and a camera-tracking pass gave the same verdict.

## Verdict

**Renders, visually identifiable (allowed in the task vocabulary):**
`cow` (brown/white), `pig` (pink), `sheep` (white, woolly), `chicken` (small white),
`wolf` (grey/white), `mooshroom` (red with white spots), `polar_bear` (large white),
`turtle` (green), `panda` (black/white), `iron_golem` (large stone, vines), `squid` (dark).

**Entity exists and is tracked, but nothing is drawn (excluded):**
`rabbit`, `fox`, `llama`, `horse`, `cat`, `ocelot`, `bee`, `villager`, `zombie`,
`skeleton`, `creeper`, `spider`, `enderman`, `witch`, `pillager`, `slime`.

All 27 tested mobs *are* present in `prismarine-viewer/viewer/lib/entity/entities.json`
(94 entries), and the bot found every one of them as a live entity (`NO_ENTITY` count 0) —
so this is a renderer texture/material gap, not a spawn failure. The pattern is that
quadruped-style models draw and humanoid/insect/amorphous ones do not.

## Consequences applied

- The v9/v10 sessions killed zombies, spiders, skeletons, foxes, rabbits and llamas and
  showed villagers. Those events were **invisible** in the video. Dropped.
- Night combat is dropped with them (all hostiles are invisible), so the session stays in
  daylight where block textures read clearly.
- Villagers are replaced by an `iron_golem` as the village's visible inhabitant.

## Second finding: magenta boxes are dropped items, not mobs

The magenta cubes littering earlier footage are item entities with missing textures (a
mob's drops), not untextured mobs. Fixed with `/gamerule doTileDrops false`.

## Third finding: `/fill` and `/tp` need a loaded chunk

Teleporting to far coordinates lands in unloaded chunks, so `/fill` is refused and the bot
drops wherever it lands — which in v10 was repeatedly the sea, and translucent water washed
whole minutes of footage blue. Fix: teleport high above the target column first (loads the
chunk), then scan the column for a *dry* surface block and teleport onto it (`landDry`).
