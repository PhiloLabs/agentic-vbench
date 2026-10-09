#!/bin/bash
# Pre-agent stage: copy the pre-baked broadcast and label space into the agent's workspace.
set -euo pipefail

mkdir -p /workspace/materials /workspace/output /workspace/work
cp /baked/match.mp4 /workspace/materials/match.mp4
cp /baked/vocabulary.json /workspace/materials/vocabulary.json

mkdir -p /logs/artifacts
ls -la /workspace/materials/ > /logs/artifacts/materials-listing.txt

rm -- "$0"
