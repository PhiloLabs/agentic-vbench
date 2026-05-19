#!/bin/bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"

mkdir -p /workspace/materials /workspace/output /workspace/work
cp "$HERE/corrupted.mp4" /workspace/materials/corrupted.mp4

if [ ! -s /workspace/materials/corrupted.mp4 ]; then
    echo "ERROR: corrupted.mp4 missing or empty" >&2
    exit 1
fi

mkdir -p /logs/artifacts
ffprobe -v error -show_entries stream=nb_read_frames,r_frame_rate,duration \
        -count_frames -select_streams v:0 \
        /workspace/materials/corrupted.mp4 \
        > /logs/artifacts/input-probe.txt 2>&1 || true

rm -rf -- "$HERE/corrupted.mp4" "$0"
