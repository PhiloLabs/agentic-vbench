# Reconstruct The Deferred Requests In A Multiplayer Building Session

You are given one video at `/workspace/materials/session.mp4`: a nearly four-hour first-person
recording of one player in a multiplayer Minecraft server session. Two players work
together on shared builds and talk to each other over live voice chat, which is on the
video's audio track.

An offline speech-to-text tool is installed. It prints timestamped segments (seconds
from the start of the video) and does not label speakers:

```
transcribe /workspace/materials/session.mp4                        # whole session
transcribe /workspace/materials/session.mp4 --start 600 --end 900  # one stretch
```

`ffmpeg` and `ffprobe` are available for sampling frames and audio.

## What to report

Throughout the session the players ask each other to do things. Many requests are acted
on straight away. **Those are not what this task is about.**

Report every request that was **not acted on within 15 seconds of being spoken, but was
carried out later.** For each one, reconstruct what eventually happened.

A request counts only when a player, speaking on voice, asks the **other player** for a
concrete, externally observable in-game action. Do not count:

- requests acted on promptly — if visible execution begins within 15 seconds of the
  words, the request is out of scope;
- requests that are never carried out at all anywhere in the recording;
- anything said to the pet pig or to other mobs;
- text read aloud from chat, or from a wish list;
- questions that ask for information rather than action;
- the speaker describing their own plan ("I'm going to finish the roof");
- banter, jokes, and bare acknowledgements;
- praise or commentary about something the other player has *already* done.

## What each entry must contain

- `command_time_s` — seconds from video start at which the request is spoken.
- `speaker` / `target` — who asks, and who is asked.
- `action` / `object` — what is asked for, using the closed vocabularies below.
- `executor` — the player who **visibly performs** the action.
- `execution_start_s` — seconds at which the visible execution begins. By the definition
  of this task it is at least 15 seconds after `command_time_s`; it can be several
  minutes after, and the player may go elsewhere and come back before doing it.
- `outcome` — one of:
  - `completed` — the requested action is visibly done as asked;
  - `partial` — visibly started but never finished as asked;
  - `corrected` — done wrong first, then fixed during the session.
- `evidence_start_s` / `evidence_end_s` — the video interval that shows the execution.

Base `executor`, `execution_start_s` and `outcome` only on what is visible in this
recording. A request whose execution you cannot actually see is not one to report.

## Closed vocabularies

- players ∈ { nio, thatdeath }  (plus `group` for a request to everyone, and `unknown`
  if you truly cannot tell who spoke or was addressed)
- `action` ∈ { break, bring, catch, collect, come, craft, eat, fetch, fill, find, fly, get, give, glide, go, grab, hang, hold, leash, lock, name, place, push, put, remove, retry, splash, stand, throw, turn, wait }
- `object` ∈ { bamboo, banner, bed, block, boat, bread, brush, bucket, ceiling, coarse_dirt, door, eggs, empty_item_frames, fish, flight, flower_pot, hill, item_frame, jungle_wood, lamp, lead, light, painting, pig, pigs, potion, quartz_block, river_water, room, route, spyglass, string, vines, wall, water, window, wool }

## Output

Write your answer to `/workspace/output/solution.json`:

```json
{
  "commands": [
    {
      "command_time_s": 5500.0,
      "speaker": "nio",
      "target": "thatdeath",
      "action": "bring",
      "object": "bucket",
      "executor": "thatdeath",
      "outcome": "completed",
      "execution_start_s": 5572.0,
      "evidence_start_s": 5568.0,
      "evidence_end_s": 5595.0
    }
  ]
}
```

The entry above only shows the shape. It is made up — it is not one of the requests
in this recording, and neither its timestamps nor its fields should appear in your
answer unless you independently find such a request.

Times are in seconds from the start of the video. `command_time_s` is matched within
5 seconds and `execution_start_s` within 10 seconds; your evidence interval must
substantially overlap the interval in which the execution is actually visible. There is
no fixed number of entries — report exactly those you find.
