#!/bin/bash
set -euo pipefail

mkdir -p /workspace/materials /workspace/output /workspace/work /logs/artifacts
cp /baked/final.mp4 /workspace/materials/final.mp4
ffprobe -v error -show_entries format=duration:stream=width,height,r_frame_rate \
    -of json /workspace/materials/final.mp4 > /logs/artifacts/media-probe.json
rm -- "$0"
