# Remove A Segment From A Video

The video at `/workspace/materials/source.mp4` has a specific segment
I'd like removed. Read the prompt below — that's the part I want gone.
Keep everything else exactly as it is, and make sure the cut is smooth:
where the segment used to be, the surrounding content should join up
cleanly without a jarring jump.

## What I noticed

The number of active aircraft carriers stated in this clip has a stats
error. Please cut out that area and keep the rest of the content
unchanged.

## What to deliver

- `/workspace/output/output.mp4` — H.264 / yuv420p, AAC audio, same
  resolution as the input. Video and audio stay in sync (cut both
  together).
- `/workspace/output/cuts.json` — the cut you made:
  ```json
  {"cuts": [{"start_ms": 12000, "end_ms": 38500, "reason": "stats error"}]}
  ```
  Time offsets in milliseconds from the **input** video.

## Environment

- CPU only, ~30 min timeout. Internet available for `pip install`.
