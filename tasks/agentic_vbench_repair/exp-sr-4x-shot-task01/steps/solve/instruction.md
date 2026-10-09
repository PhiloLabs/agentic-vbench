# Restore A Section Of Lower-Quality Footage

I have a short clip where, at one stretch, the picture quality drops —
it gets softer / less detailed for a few seconds, then snaps back to
normal. The rest of the clip looks clean and sharp.

Please find that stretch and bring the quality up so it matches the
rest of the clip — same level of detail, no obvious artifacts. Leave
everything else untouched.

A short hint at what I'm noticing is in `/workspace/materials/prompt.txt`.

## What to deliver

- `/workspace/output/output.mp4` — H.264 / yuv420p, same dimensions,
  frame rate, and total number of frames as the input. Video-only is
  fine.
- `/workspace/output/output.json` — the degraded interval you identified
  in the input video, using this format:

  ```json
  {
    "start_frame": 100,
    "end_frame": 199
  }
  ```

  Use integer, zero-based frame indices from the input video. Both
  endpoints are inclusive: this example identifies frames 100 through
  199 (100 frames). The numbers are illustrative, not the task's answer.
  The range must satisfy `0 <= start_frame <= end_frame < N`, where `N`
  is the input video's total frame count. Report the section whose quality
  was degraded, rather than every frame affected by re-encoding.

## Environment

- CPU only, ~30 min timeout. Internet available for `pip install`.

