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

## Environment

- CPU only, ~30 min timeout. Internet available for `pip install`.
