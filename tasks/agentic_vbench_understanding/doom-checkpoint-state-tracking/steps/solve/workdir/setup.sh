#!/bin/bash
set -euo pipefail

mkdir -p /workspace/materials /workspace/output /workspace/work
cp /baked/doom-checkpoint-state-tracking.mp4 \
    /workspace/materials/doom-checkpoint-state-tracking.mp4
chmod 0444 /workspace/materials/doom-checkpoint-state-tracking.mp4

mkdir -p /logs/artifacts
sha256sum /workspace/materials/doom-checkpoint-state-tracking.mp4 \
    > /logs/artifacts/materials.sha256
ffprobe -v error -show_entries \
    stream=width,height,avg_frame_rate,nb_frames:format=duration \
    -of json /workspace/materials/doom-checkpoint-state-tracking.mp4 \
    > /logs/artifacts/media-probe.json

rm -- "$0"
