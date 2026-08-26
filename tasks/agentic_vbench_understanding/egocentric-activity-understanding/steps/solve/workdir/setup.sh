#!/bin/bash
# Pre-agent stage: copy the pre-baked session and label space into the agent's workspace.
set -euo pipefail

mkdir -p /workspace/materials /workspace/output /workspace/work
cp /baked/session.mkv /workspace/materials/session.mkv
cp /baked/vocabulary.json /workspace/materials/vocabulary.json

mkdir -p /logs/artifacts
ls -la /workspace/materials/ > /logs/artifacts/materials-listing.txt

rm -- "$0"
