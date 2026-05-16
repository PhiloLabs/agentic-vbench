# Frozen-Frame Fix

I have a video that stutters at a couple of spots — the picture freezes in
place for a stretch, the action stops, then it picks up again. Outside
those spots the playback is smooth. The audio may or may not stay in sync
through the stuck parts.

Find the frozen stretches and cut them out cleanly so the surrounding
content joins smoothly, with audio and video in sync from start to end.
Don't try to fill in motion that isn't there; just remove the redundant
frames.

## What to deliver

- `/workspace/output/output.mp4` — H.264 / yuv420p, same fps and
  dimensions as the input. Audio track (AAC) preserved. Length should
  equal the input length minus the duration of what you removed.
- `/workspace/output/cuts.json` — list of the frozen stretches you
  removed:
  ```json
  {
    "glitches": [
      {"type": "duplicated", "start_frame": S, "end_frame": E}
    ]
  }
  ```
  `start_frame` / `end_frame` are 0-indexed frame numbers in the **input**
  video; inclusive start, exclusive end (the range `[S, E)` is what you
  removed).

## Environment

- CPU only, ~30 min timeout. Internet available for `pip install`.
