#!/bin/bash
set -euo pipefail

mkdir -p /workspace/materials /workspace/output /workspace/work
cp /baked/debate.mp4 /workspace/materials/debate.mp4
cp /baked/roster.json /workspace/materials/roster.json
cp /baked/excerpts.json /workspace/materials/excerpts.json
cp -a /baked/roster /workspace/materials/roster

rm -- "$0"
