# LoL Minimap Timeline + Economy Reconstruction

You are given one video at `/workspace/materials/minimap_vod.mp4`: the **map view
only** of one full League of Legends game (spectator, full-map vision), recorded
real time from game start 0:00. There is no main camera, HUD, clock, killfeed,
scoreboard, names, gold, or objective-spawn timers — only the minimap. An event's
`game_clock_s` is its elapsed seconds in the video (read frame time from the video
itself; no on-screen clock is shown).

Reconstruct every key event of the game in chronological order. Each event is a
5-tuple `(game_clock_s, type, entity, minute_gain, leader_before)`.

- `type`: one of `champion_kill | tower_kill | epic_monster_kill`
- `game_clock_s`: integer seconds (elapsed video time)
- `entity` depends on type:
  - `champion_kill` → the dead champion's official English name exactly as written
    on leagueoflegends.com/champions, including apostrophes and capitalization
    (e.g. `Ahri`, `Kai'Sa`, `Cho'Gath`). Matching ignores case only.
  - `tower_kill` → a TURRET only (ignore inhibitors). `"{team}_{lane}_{tier}"`,
    where team is `blue|red` (the side that destroyed it), lane is `top|mid|bot`,
    or `base` for the two Nexus turrets, and tier is `outer|inner|inhib|nexus`.
    The two Nexus turrets are both `"{team}_base_nexus"` — do not distinguish
    left/right. Examples: `red_top_outer`, `blue_base_nexus`.
  - `epic_monster_kill` → the specific monster: a drake element
    `infernal|ocean|mountain|cloud|hextech|chemtech`, or `elder` (elder dragon),
    or `baron` (dragons and Baron are the SAME type; the entity says which).
- `minute_gain`: `blue|red|equal` — which side gained more gold (≥300 net) during
  the game-minute containing the event, else `equal`.
- `leader_before`: `blue|red|equal` — which side led (by ≥1000 gold) at the whole
  minute just before the event, else `equal`.

On the map: champion icons are portraits (identity is readable), structures are
fixed icons that vanish permanently when destroyed, and vision is full-map, so a
champion icon disappearing is a death (it reappears at the fountain after the
respawn timer), not fog. Blue base is bottom-left, red base is top-right. No gold
is ever shown — the two economy fields must be inferred from map macro (who took
the kills/towers/objectives, who held wave and map pressure, the cumulative state
of towers/control/vision up to that point).

IGNORE inhibitors: do NOT report inhibitor structures at all. Only turrets are
`tower_kill` events.

## What to submit

Write `/workspace/output/solution.json` in exactly this shape (the example values
are made-up, not from this game):

```json
{
  "events": [
    {"game_clock_s": 196, "type": "champion_kill", "entity": "Taliyah", "minute_gain": "blue", "leader_before": "equal"},
    {"game_clock_s": 380, "type": "epic_monster_kill", "entity": "chemtech", "minute_gain": "equal", "leader_before": "blue"},
    {"game_clock_s": 826, "type": "tower_kill", "entity": "red_top_outer", "minute_gain": "red", "leader_before": "blue"}
  ]
}
```

- One entry per key event, in any order.
- This game has 111 events: 86 `champion_kill`, 16 `tower_kill`, 9
  `epic_monster_kill` (6 drakes, 3 barons). Blue: Garen, Zac, Ahri, Kai'Sa, Thresh;
  red: Vayne, Sejuani, Yone, Taliyah, Neeko.

## Rules

- Stay inside this working directory. Do not read, write, or search outside it.
- Do not look anything up online, and do not rely on memory of any game; find every
  event in the video. This is a private game with no public timeline.
- Watch the entire video carefully, using every tool available to you (`ffmpeg`,
  `ffprobe`, frame extraction, etc.). Do not stop early — confirm you have covered
  the whole game before you answer.
