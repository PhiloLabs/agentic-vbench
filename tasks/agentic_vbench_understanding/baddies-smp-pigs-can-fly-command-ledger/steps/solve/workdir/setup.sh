#!/bin/bash
# Pre-agent stage: copy the pre-baked session into the agent's workspace.
set -euo pipefail

mkdir -p /workspace/materials /workspace/output /workspace/work
cp /baked/session.mp4 /workspace/materials/session.mp4

mkdir -p /logs/artifacts
ls -la /workspace/materials/ > /logs/artifacts/materials-listing.txt

rm -- "$0"
