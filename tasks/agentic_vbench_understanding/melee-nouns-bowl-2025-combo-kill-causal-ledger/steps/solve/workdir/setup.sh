#!/bin/bash
set -euo pipefail

mkdir -p /workspace/materials /workspace/output /workspace/work /logs/artifacts
sha256sum /baked/match.mp4 > /logs/artifacts/baked-match.sha256
ffprobe -v error -select_streams v:0 \
  -show_entries stream=width,height,r_frame_rate,nb_frames \
  -show_entries format=duration,size \
  -of default=noprint_wrappers=1 /baked/match.mp4 \
  > /logs/artifacts/baked-match.ffprobe.txt
mv /baked/match.mp4 /workspace/materials/match.mp4
sha256sum /workspace/materials/match.mp4 > /logs/artifacts/agent-match.sha256
test ! -e /baked/match.mp4
ls -la /workspace/materials > /logs/artifacts/materials-listing.txt
rm -- "$0"
