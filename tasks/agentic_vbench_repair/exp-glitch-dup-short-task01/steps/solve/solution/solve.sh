#!/bin/bash
# Oracle solver: baked-in GT cut points. Uses ffmpeg select filter to
# drop the duplicate copy of each GT glitch block, then writes
# output.mp4 + cuts.json.
set -euo pipefail

mkdir -p /workspace/output /workspace/work

INPUT=/workspace/materials/corrupted.mp4
OUTPUT=/workspace/output/output.mp4
OUTPUT_CUTS=/workspace/output/cuts.json

# Baked-in GT (post-injection frame indices in corrupted.mp4):
cat > "$OUTPUT_CUTS" <<'JSONEOF'
{
  "glitches": [
    {
      "type": "duplicated",
      "start_frame": 557,
      "end_frame": 574
    },
    {
      "type": "duplicated",
      "start_frame": 2737,
      "end_frame": 2754
    }
  ]
}
JSONEOF

# Source fps as a rational; pass through to -r and use a guarded
# `setpts=N/(FPS)/TB` (parens so fractional FPS like 24000/1001 isn't
# parsed as `N/24000/1001/TB`).
FPS=50/1

# Build ffmpeg select expression: keep frame n iff n not in any [s, e).
# Each glitch contributes a sub-expr "between(n,s,e-1)"; we OR them and negate.
SELECT_EXPR='not(between(n\,557\,573)+between(n\,2737\,2753))'

# Audio cut spans (time, in seconds, in input). Each freeze block at
# post-injection frames [s, e) corresponds to audio span
# [s/FPS, e/FPS). We drop those audio samples so audio stays in sync
# with the cleaned video.
ASELECT_EXPR='not(between(t\,11.140000\,11.480000)+between(t\,54.740000\,55.080000))'

ffmpeg -y -i "$INPUT" \
    -vf "select=${SELECT_EXPR},setpts=N/(${FPS})/TB" \
    -af "aselect=${ASELECT_EXPR},asetpts=N/SR/TB" \
    -r "${FPS}" \
    -c:v libx264 -pix_fmt yuv420p -preset veryfast \
    -c:a aac -ac 1 -ar 16000 \
    "$OUTPUT"

echo "oracle: wrote $OUTPUT and $OUTPUT_CUTS"
