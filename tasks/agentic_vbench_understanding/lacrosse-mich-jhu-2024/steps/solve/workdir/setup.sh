#!/bin/bash
# Pre-agent stage: copy the pre-baked, hash-verified materials into the
# agent's workspace. The answer key and grader are NOT here — they are mounted
# only for the solution/verifier steps.
set -euo pipefail

mkdir -p /workspace/materials /workspace/output /workspace/work
cp /baked/game.mp4    /workspace/materials/game.mp4
cp /baked/roster.json /workspace/materials/roster.json
cp /baked/schema.json /workspace/materials/schema.json

mkdir -p /logs/artifacts
ls -la /workspace/materials/ > /logs/artifacts/materials-listing.txt

rm -- "$0"
