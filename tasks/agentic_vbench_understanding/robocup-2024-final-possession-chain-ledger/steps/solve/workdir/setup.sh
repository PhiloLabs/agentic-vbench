#!/bin/bash
set -euo pipefail

mkdir -p /workspace/materials /workspace/output /workspace/work /logs/artifacts
cp /baked/match.mp4 /workspace/materials/match.mp4
ls -la /workspace/materials > /logs/artifacts/materials-listing.txt
rm -- "$0"
