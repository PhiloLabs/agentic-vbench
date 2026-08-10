# Doom gameplay event and state reconstruction

You are given one silent first-person Doom gameplay video:

`/workspace/materials/doom-checkpoint-state-tracking.mp4`

It contains six episodes separated by two-second black gaps. Reconstruct every
scored interaction in order and the complete player and world state immediately
after it.

## Visual identities

- Key cards are `blue_key`, `yellow_key`, and `red_key`.
- Weapons are `shotgun`, `chaingun`, `rocket_launcher`, and `plasma_rifle`.
- Switch panels use fixed glyphs: amber circle is `switch_amber`, cyan triangle
  is `switch_cyan`, violet diamond is `switch_violet`, and white cross is
  `switch_white`. A bright glyph is on; a dim glyph is off.
- The green star is `checkpoint_alpha`; the blue hexagon is
  `checkpoint_beta`.
- Blue, yellow, and red lock panels are `door_blue`, `door_yellow`, and
  `door_red`.
- The cyan-violet portal is `episode_exit`.

Health, ammo, and armor pickups not listed above are unscored distractors.
Looking at an object without collecting or activating it is unscored. Failed
door and switch uses are unscored.

## Scored events

- `key_pickup`: first frame after the key sprite is collected.
- `weapon_pickup`: first frame on which the collected weapon becomes active.
- `switch_activate`: first frame after a successful off-to-on switch use.
- `checkpoint_activate`: first frame after a checkpoint becomes current.
- `locked_door_open`: first frame on which a keyed door begins opening.
- `checkpoint_restore`: first restored frame showing the arrival effect.
- `level_exit`: first frame of the exit transition.

The event entity is the collected key or weapon, activated switch or checkpoint,
opened door, current checkpoint for a restore, or `episode_exit` for an exit.

Each episode begins with `pistol`, no keys, no active switches, no open doors,
and a null checkpoint. Keys are not consumed. Open doors never close. Key and
weapon pickups, doors, and checkpoints score at most once per episode. A switch
can score again only after a checkpoint restore has reverted it to off.

Activating a checkpoint saves the complete active-switch set. On restore, held
keys, the active weapon, open doors, and the current checkpoint persist, while
active switches revert to the saved set. The exit is the final event and keeps
the state visible at transition start.

Timestamps are non-negative integer milliseconds from the first non-black frame
of that episode. They must be non-decreasing. Use the first visible event frame;
timestamps within 750 ms of that frame are accepted.

## Output

Write `/workspace/output/solution.json` with exactly this shape:

```json
{
  "episodes": [
    {
      "episode_id": "episode_01",
      "events": [
        {
          "timestamp_ms": 12345,
          "event_type": "key_pickup",
          "entity_id": "blue_key",
          "state": {
            "active_weapon": "pistol",
            "held_keys": ["blue_key"],
            "active_switches": [],
            "open_doors": [],
            "current_checkpoint": null
          }
        }
      ]
    }
  ]
}
```

Episode IDs are `episode_01` through `episode_06` in video order and each must
appear once. State arrays are duplicate-free subsets of the vocabularies above;
their order is insignificant. Objects accept exactly the shown keys and no
extras.

Stay inside the working directory. Do not use the internet or prior knowledge
to fabricate answers; ground every event in the supplied video.
