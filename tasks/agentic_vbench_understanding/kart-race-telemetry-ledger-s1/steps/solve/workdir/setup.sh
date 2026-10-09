#!/bin/bash
set -euo pipefail
mkdir -p /workspace/materials /workspace/output /workspace/work
cp /baked/race.mp4 /workspace/materials/race.mp4
mkdir -p /logs/artifacts
ls -la /workspace/materials/ > /logs/artifacts/materials-listing.txt
rm -- "$0"
