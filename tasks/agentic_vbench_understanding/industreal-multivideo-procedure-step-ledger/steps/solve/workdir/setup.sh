#!/bin/bash
set -euo pipefail

mkdir -p /workspace/materials /workspace/output /workspace/work /logs/artifacts
cp /baked/materials/*.mp4 /workspace/materials/
cp /baked/reference/overview-of-states.pdf /workspace/materials/
ls -la /workspace/materials/ > /logs/artifacts/materials-listing.txt

rm -- "$0"
