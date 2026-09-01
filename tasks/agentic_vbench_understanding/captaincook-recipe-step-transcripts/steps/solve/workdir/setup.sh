#!/bin/bash
# Pre-agent stage: copy the pre-baked recordings into the agent's workspace.
#
# The clips are named A.mp4 through V.mp4 and carry no recording identifiers: the bake
# step in environment/Dockerfile strips container metadata, chapters, and any audio, data
# or subtitle stream. The count is asserted here rather than assumed, because an agent
# handed 21 of 22 clips would answer the 21 it can see and the missing one would show up
# only as a low score.
set -euo pipefail

mkdir -p /workspace/materials /workspace/output /workspace/work
cp /baked/*.mp4 /workspace/materials/

n=$(find /workspace/materials -name '*.mp4' -size +0c | wc -l | tr -d ' ')
test "$n" -eq 22 || { echo "expected 22 recordings in /workspace/materials, found $n" >&2; exit 1; }

mkdir -p /logs/artifacts
ls -la /workspace/materials/ > /logs/artifacts/materials-listing.txt

rm -- "$0"
