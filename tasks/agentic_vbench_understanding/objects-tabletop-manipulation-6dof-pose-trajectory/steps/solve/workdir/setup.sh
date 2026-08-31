#!/bin/bash
# Pre-agent stage: stage the baked clips + camera models + query/object lists into the
# agent's workspace. The ground-truth poses are NOT copied here.
set -euo pipefail

mkdir -p /workspace/materials /workspace/output /workspace/work
cp /baked/clip_01.mp4 /workspace/materials/clip_01.mp4
cp /baked/clip_02.mp4 /workspace/materials/clip_02.mp4
cp /baked/clip_03.mp4 /workspace/materials/clip_03.mp4
cp /baked/cameras.json /workspace/materials/cameras.json
cp /baked/queries.json /workspace/materials/queries.json
cp /baked/objects.json /workspace/materials/objects.json
cp /baked/object_points.json /workspace/materials/object_points.json

mkdir -p /logs/artifacts
ls -la /workspace/materials/ > /logs/artifacts/materials-listing.txt

rm -- "$0"
