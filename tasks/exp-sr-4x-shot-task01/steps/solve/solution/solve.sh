#!/bin/bash
# Oracle: copy the bundled golden + emit GT shot range JSON.
# Ceiling-proof oracle for SR family.
set -euo pipefail
mkdir -p /workspace/output
HERE="$(cd "$(dirname "$0")" && pwd)"
cp "$HERE/original.mp4" /workspace/output/output.mp4
cat > /workspace/output/output.json <<'EOF'
{"start_frame": 655, "end_frame": 792}
EOF
echo "oracle: copied bundled golden $HERE/original.mp4 -> /workspace/output/output.mp4"
