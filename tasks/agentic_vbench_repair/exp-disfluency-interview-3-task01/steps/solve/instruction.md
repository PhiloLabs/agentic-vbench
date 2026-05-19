# Smooth Out An Interview Clip

I have a short clip from a real interview at
`/workspace/materials/source.mp4`. The speaker has one very visible
hesitant moment — a stuck-up jitter / disfluency that interrupts the
flow of what she's saying. The rest of what she says I want to keep
exactly as it is; her expression and the meaning of every sentence
should be preserved. I just want that one rough spot trimmed so the
chat reads more smoothly.

Find the one hesitant moment and cut it out. After the cut, what came
before and what comes after should connect naturally — same pacing,
same voice, just without the jitter. Don't remove anything else.

## What to deliver

- `/workspace/output/output.mp4` — H.264 / yuv420p, AAC audio, same
  resolution as the input. Video and audio in sync (cut both together).
- `/workspace/output/cuts.json` — the cut you made:
  ```json
  {"cuts": [{"start_ms": 12480, "end_ms": 12720, "reason": "hesitation"}]}
  ```
  Time offsets in milliseconds from the **input** video.

## Environment

- CPU only, ~30 min timeout. Internet available for `pip install`.
