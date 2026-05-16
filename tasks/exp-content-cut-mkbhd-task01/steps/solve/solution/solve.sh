#!/bin/bash
# Oracle solver: 1 cut, per-endpoint tolerance 0.1s start / 0.2s end.
set -euo pipefail

mkdir -p /workspace/output /workspace/work
INPUT=/workspace/materials/source.mp4
OUTPUT=/workspace/output/output.mp4
OUTPUT_CUTS=/workspace/output/cuts.json

cat > "$OUTPUT_CUTS" <<'JSONEOF'
{
  "cuts": [
    {"start_ms": 29143, "end_ms": 34328, "reason": "off-topic segment per prompt"}
  ]
}
JSONEOF

ffmpeg -y -i "$INPUT" \
    -vf "select='not(between(t\,29.143\,34.328))',setpts=N/FRAME_RATE/TB" \
    -af "aselect='not(between(t\,29.143\,34.328))',asetpts=N/SR/TB" \
    -c:v libx264 -pix_fmt yuv420p -preset veryfast \
    -c:a aac -ac 1 -ar 16000 \
    "$OUTPUT"

echo "oracle: wrote $OUTPUT and $OUTPUT_CUTS"
