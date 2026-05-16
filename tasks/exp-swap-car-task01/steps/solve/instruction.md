# Restore A Video's Shot Order

I have a multi-shot video at `/workspace/materials/corrupted.mp4`. Two
of the shots ended up in the wrong positions on the timeline — somewhere
along the way they got placed in each other's slots. You can usually
tell from context: the story doesn't flow right at those two spots.

Please figure out which two shots got mixed up and put them back in
their original positions. The rest of the video should pass through
unchanged.

## What to deliver

- `/workspace/output/output.mp4` — H.264 / yuv420p video + AAC 48 kHz
  stereo audio, same dimensions, frame rate, and total length as the
  input. The audio for each shot must travel with that shot when you
  move them.
- `/workspace/output/output.json` — the two shot ranges you identified
  as misplaced (their positions in the **input** as you found them):
  ```json
  {
    "swap": [
      {"corrupted_start": Sa, "corrupted_end": Ea},
      {"corrupted_start": Sb, "corrupted_end": Eb}
    ]
  }
  ```
  Frame indices in the input video; inclusive start, exclusive end.
  Order in the list doesn't matter.

## Environment

- CPU only, ~30 min timeout. Internet available for `pip install`.
