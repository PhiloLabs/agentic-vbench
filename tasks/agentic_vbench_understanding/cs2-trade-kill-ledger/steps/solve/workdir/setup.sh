#!/bin/bash
# Pre-agent stage: copy the pre-baked POV renders into the agent's workspace.
set -euo pipefail

mkdir -p /workspace/materials /workspace/output /workspace/work
for k in $(seq 1 10); do
    cp "/baked/P${k}.mp4" "/workspace/materials/P${k}.mp4"
done

mkdir -p /logs/artifacts
ls -la /workspace/materials/ > /logs/artifacts/materials-listing.txt

rm -- "$0"
