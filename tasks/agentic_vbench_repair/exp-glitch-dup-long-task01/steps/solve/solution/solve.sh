#!/bin/bash
# Oracle solver: drop the GT glitch ranges using the EXACT same ffmpeg
# invocation the verifier's _reconstruct_remainder uses for the honesty
# gate (preset ultrafast, crf 20, time-based select, aac 128k, +faststart).
# The earlier `-preset veryfast` + frame-based select + 16k mono audio
# produced an output that drifted from the verifier's reconstruction by
# enough to land SSIM at 0.887 — below the 0.95 honesty gate, so the
# oracle scored 0.
set -euo pipefail

mkdir -p /workspace/output /workspace/work

INPUT=/workspace/materials/corrupted.mp4
OUTPUT=/workspace/output/output.mp4
OUTPUT_CUTS=/workspace/output/cuts.json

# Baked-in GT (post-injection frame indices in corrupted.mp4):
cat > "$OUTPUT_CUTS" <<'JSONEOF'
{
  "glitches": [
    {"type": "duplicated", "start_frame": 152, "end_frame": 179},
    {"type": "duplicated", "start_frame": 356, "end_frame": 383}
  ]
}
JSONEOF

# Convert frame ranges to time the same way _parse_ranges does — closed
# `between(t,s,e)` with a half-frame nudge on the end (0.5/fps) so the
# half-open semantics [start_frame, end_frame) survive the closed-interval
# match:
#   fps = 24000/1001 ≈ 23.97603
#   152 / fps                = 6.339667
#   (179 - 0.5) / fps        = 7.444792
#   356 / fps                = 14.848167
#   (383 - 0.5) / fps        = 15.953292
SEL='not(between(t\,6.339667\,7.444792)+between(t\,14.848167\,15.953292))'

ffmpeg -nostdin -y -loglevel error -i "$INPUT" \
    -vf "select='${SEL}',setpts=N/FRAME_RATE/TB" \
    -af "aselect='${SEL}',asetpts=N/SR/TB" \
    -c:v libx264 -preset ultrafast -crf 20 -pix_fmt yuv420p \
    -c:a aac -b:a 128k \
    -movflags +faststart \
    "$OUTPUT"

echo "oracle: wrote $OUTPUT and $OUTPUT_CUTS"
