#!/bin/bash
# Pre-agent stage: stage the baked clips + camera models + object list into the agent's
# workspace. The reference meshes and GT points are NOT copied here.
set -euo pipefail

mkdir -p /workspace/materials /workspace/output /workspace/work
cp /baked/clip_01.mp4 /workspace/materials/clip_01.mp4
cp /baked/clip_02.mp4 /workspace/materials/clip_02.mp4
cp /baked/clip_03.mp4 /workspace/materials/clip_03.mp4
cp /baked/cameras.json /workspace/materials/cameras.json
cp /baked/objects.json /workspace/materials/objects.json

mkdir -p /logs/artifacts
ls -la /workspace/materials/ > /logs/artifacts/materials-listing.txt

rm -- "$0"
