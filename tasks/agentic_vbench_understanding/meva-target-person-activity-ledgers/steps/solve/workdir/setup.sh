#!/bin/bash
set -euo pipefail

mkdir -p /workspace/materials /workspace/output /workspace/work
cp /baked/meva_activity_montage.mp4 /workspace/materials/meva_activity_montage.mp4
cp /baked/roster.json /workspace/materials/roster.json
cp -a /baked/roster /workspace/materials/roster

rm -- "$0"
