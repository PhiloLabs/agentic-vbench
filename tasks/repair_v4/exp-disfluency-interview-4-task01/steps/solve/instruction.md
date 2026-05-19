# Remove Two Filler Moments From An Interview

I have a short interview clip at `/workspace/materials/source.mp4` with
two very brief "emmm" filler moments — quick, instant hesitations that
interrupt the speaker's flow. Each one is just a hummed filler; removing
them shouldn't change anything else about the delivery. I want both gone
so the speech reads more smoothly.

Find those two "emmm" moments and cut them out. After the cuts, the
words on either side should join naturally — same voice, same content,
just tighter. Don't remove any other words.

## What to deliver

- `/workspace/output/output.mp4` — H.264 / yuv420p, AAC audio, same
  resolution as the input. Video and audio in sync (cut both together).
- `/workspace/output/cuts.json` — your two cuts:
  ```json
  {"cuts": [
    {"start_ms": 5666,  "end_ms": 6556,  "reason": "filler 'emmm'"},
    {"start_ms": 23076, "end_ms": 23607, "reason": "filler 'emmm'"}
  ]}
  ```
  Time offsets in milliseconds from the **input** video.

## Environment

- CPU only, ~30 min timeout. Internet available for `pip install`.
