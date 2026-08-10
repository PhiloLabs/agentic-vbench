#!/bin/bash
set -euo pipefail

mkdir -p /workspace/materials /workspace/output /workspace/work
cp /baked/game.mp4 /workspace/materials/game.mp4
cp /baked/court-grid.png /workspace/materials/court-grid.png

mkdir -p /logs/artifacts
ls -la /workspace/materials/ > /logs/artifacts/materials-listing.txt

rm -- "$0"
