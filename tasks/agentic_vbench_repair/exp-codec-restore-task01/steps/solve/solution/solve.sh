#!/bin/bash
# Oracle: copy the pre-baked golden into the agent-output path.
# Golden was baked into /baked/golden/ at `docker build` time.
set -euo pipefail
mkdir -p /workspace/output
cp /baked/golden/clean.wav /workspace/output/enhanced.wav
echo "oracle: copied /baked/golden/clean.wav -> /workspace/output/enhanced.wav"
