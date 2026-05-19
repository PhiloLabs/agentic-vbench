#!/bin/bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"

mkdir -p /workspace/materials /workspace/output /workspace/work
cp "$HERE/source.mp4" /workspace/materials/source.mp4

if [ ! -s /workspace/materials/source.mp4 ]; then
    echo "ERROR: source.mp4 missing or empty" >&2
    exit 1
fi

mkdir -p /logs/artifacts
ffprobe -v error -show_entries stream=duration,r_frame_rate \
        -select_streams v:0 \
        /workspace/materials/source.mp4 \
        > /logs/artifacts/input-probe.txt 2>&1 || true

rm -rf -- "$HERE/source.mp4" "$0"
