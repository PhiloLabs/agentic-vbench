# Remove A Segment From A Video

The video at `/workspace/materials/source.mp4` has a specific segment
I'd like removed. Read the prompt below — that's the part I want gone.
Keep everything else exactly as it is, and make sure the cut is smooth:
where the segment used to be, the surrounding content should join up
cleanly without a jarring jump.

## What I noticed

The video makes a claim about the phone case helping the phone stand up
reliably, but I've found this isn't always true. Please remove that
specific segment.

## What to deliver

- `/workspace/output/output.mp4` — H.264 / yuv420p, AAC audio, same
  resolution as the input. Video and audio stay in sync (cut both
  together).
- `/workspace/output/cuts.json` — the cut you made:
  ```json
  {"cuts": [{"start_ms": 12000, "end_ms": 38500, "reason": "off-topic segment"}]}
  ```
  Time offsets in milliseconds from the **input** video.

## Environment

- CPU only, ~30 min timeout. Internet available for `pip install`.
