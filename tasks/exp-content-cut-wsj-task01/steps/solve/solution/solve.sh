#!/bin/bash
# Oracle solver: 1 cut, per-endpoint tolerance 0.2s.
set -euo pipefail

mkdir -p /workspace/output /workspace/work
INPUT=/workspace/materials/source.mp4
OUTPUT=/workspace/output/output.mp4
OUTPUT_CUTS=/workspace/output/cuts.json

cat > "$OUTPUT_CUTS" <<'JSONEOF'
{
  "cuts": [
    {"start_ms": 54937, "end_ms": 67300, "reason": "off-topic China-shipbuilding aside"}
  ]
}
JSONEOF

ffmpeg -y -i "$INPUT" \
    -vf "select='not(between(t\,54.937\,67.300))',setpts=N/FRAME_RATE/TB" \
    -af "aselect='not(between(t\,54.937\,67.300))',asetpts=N/SR/TB" \
    -c:v libx264 -pix_fmt yuv420p -preset veryfast \
    -c:a aac -ac 1 -ar 16000 \
    "$OUTPUT"

echo "oracle: wrote $OUTPUT and $OUTPUT_CUTS"
