#!/bin/bash
# Oracle solver: 2 fillers, per-endpoint tolerance per cut.
set -euo pipefail

mkdir -p /workspace/output /workspace/work
INPUT=/workspace/materials/source.mp4
OUTPUT=/workspace/output/output.mp4
OUTPUT_CUTS=/workspace/output/cuts.json

cat > "$OUTPUT_CUTS" <<'JSONEOF'
{
  "cuts": [
    {"start_ms": 5666,  "end_ms": 6556,  "reason": "filler 'um/emm' #1"},
    {"start_ms": 23076, "end_ms": 23607, "reason": "filler 'um/emm' #2"}
  ]
}
JSONEOF

ffmpeg -y -i "$INPUT" \
    -vf "select='not(between(t\,5.666\,6.556)+between(t\,23.076\,23.607))',setpts=N/FRAME_RATE/TB" \
    -af "aselect='not(between(t\,5.666\,6.556)+between(t\,23.076\,23.607))',asetpts=N/SR/TB" \
    -c:v libx264 -pix_fmt yuv420p -preset veryfast \
    -c:a aac -ac 1 -ar 16000 \
    "$OUTPUT"

echo "oracle: wrote $OUTPUT and $OUTPUT_CUTS"
