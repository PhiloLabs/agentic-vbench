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
  Choose the timestamps by inspecting the input clip. The following is a
  JSON Schema describing the output format, not timestamp values:
  ```json
  {
    "type": "object",
    "required": [
      "cuts"
    ],
    "properties": {
      "cuts": {
        "type": "array",
        "minItems": 2,
        "maxItems": 2,
        "items": {
          "type": "object",
          "required": [
            "start_ms",
            "end_ms",
            "reason"
          ],
          "properties": {
            "start_ms": {
              "type": "number"
            },
            "end_ms": {
              "type": "number"
            },
            "reason": {
              "type": "string"
            }
          }
        }
      }
    }
  }
  ```
  Time offsets in milliseconds from the **input** video.

## Environment

- CPU only, ~30 min timeout. Internet available for `pip install`.
