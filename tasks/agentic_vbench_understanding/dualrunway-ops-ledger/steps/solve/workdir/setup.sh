#!/bin/bash
# Pre-agent stage: copy the pre-baked video and audio into the agent's workspace.
set -euo pipefail

mkdir -p /workspace/materials /workspace/output /workspace/work
# Hard-link rather than copy: the video is ~2.3 GB and a second copy buys nothing but
# sandbox disk. Falls back to a copy if /baked and /workspace are on different devices.
ln /baked/runway.mp4 /workspace/materials/runway.mp4 2>/dev/null || cp /baked/runway.mp4 /workspace/materials/runway.mp4
ln /baked/tower.mp3 /workspace/materials/tower.mp3 2>/dev/null || cp /baked/tower.mp3 /workspace/materials/tower.mp3

mkdir -p /logs/artifacts
ls -la /workspace/materials/ > /logs/artifacts/materials-listing.txt

rm -- "$0"
