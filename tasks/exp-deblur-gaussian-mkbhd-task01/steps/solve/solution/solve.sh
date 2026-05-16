#!/bin/bash
# Oracle: copy the bundled golden reference straight to the output.
# This is the ceiling-proof oracle — it shows the verifier returns 1.0
# when given the correct answer.
set -euo pipefail
mkdir -p /workspace/output
HERE="$(cd "$(dirname "$0")" && pwd)"
cp "$HERE/clean.mp4" /workspace/output/output.mp4
echo "oracle: copied bundled golden $HERE/clean.mp4 -> /workspace/output/output.mp4"
