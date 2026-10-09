#!/bin/bash
# Pre-agent stage: copy the pre-baked broadcast into the agent's workspace.
set -euo pipefail

mkdir -p /workspace/materials /workspace/output /workspace/work
cp /baked/game.mp4 /workspace/materials/game.mp4

mkdir -p /logs/artifacts
ls -la /workspace/materials/ > /logs/artifacts/materials-listing.txt

rm -- "$0"
