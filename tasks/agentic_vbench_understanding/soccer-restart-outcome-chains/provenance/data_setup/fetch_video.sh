#!/bin/bash
# Fetch the broadcast exactly as environment/Dockerfile bakes it, and verify the digest.
# The file is YouTube format 136 of the Bundesliga's own upload (1280x720 H.264 at 25 fps,
# video only), saved as served, so its SHA256 is the publisher's own stream.
#
#   bash fetch_video.sh ./media        # -> ./media/game.mp4
set -euo pipefail

OUT=${1:?usage: fetch_video.sh <out-dir>}
YT_DLP_VERSION=2026.8.19
VIDEO_ID=U-Glif5abSY
VIDEO_FORMAT=136
SHA256=7648b622c196ca5c844eb6162dfda2532d8e46ced99728f720f62fb6d3d695e2

mkdir -p "$OUT"
python3 -m pip install --quiet "yt-dlp==${YT_DLP_VERSION}"
python3 -m yt_dlp --no-warnings --no-playlist --format "$VIDEO_FORMAT" \
    --output "$OUT/game.mp4" "https://www.youtube.com/watch?v=${VIDEO_ID}"
python3 - "$OUT/game.mp4" "$SHA256" <<'PY'
import hashlib, sys
h = hashlib.sha256()
with open(sys.argv[1], "rb") as f:
    for chunk in iter(lambda: f.read(1 << 20), b""):
        h.update(chunk)
assert h.hexdigest() == sys.argv[2], f"sha256 {h.hexdigest()} does not match the pinned {sys.argv[2]}"
print(f"{sys.argv[1]}: sha256 verified")
PY
