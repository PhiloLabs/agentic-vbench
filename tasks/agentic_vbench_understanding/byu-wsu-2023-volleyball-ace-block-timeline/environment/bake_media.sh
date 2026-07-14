#!/bin/bash
# One-time media preparation (run locally, not in Docker):
# download the pinned broadcast at >=720p, strip the audio track, and print the
# SHA256 to pin in the Dockerfile. Re-host the resulting file at a stable URL
# (e.g. a Hugging Face dataset repo) and set MATERIALS_URL/MATERIALS_SHA256.
#
# Requires: yt-dlp, ffmpeg.
set -euo pipefail

VIDEO_ID="5KC1jC90lT8"   # WSU Volleyball: #8 BYU at #13 Washington State | Full Match | 9/8/23
OUT="byu-wsu-2023-09-08-720p-noaudio.mp4"

# 720p video-only stream is sufficient (audio is stripped anyway); remux to mp4.
yt-dlp -f 'bv*[height=720][ext=mp4]/bv*[height>=720]' --remux-video mp4 \
       -o raw-720p.mp4 "https://www.youtube.com/watch?v=${VIDEO_ID}"

# Strip any audio, copy the video stream untouched, and use faststart so ffmpeg
# inside the container can seek efficiently.
ffmpeg -y -i raw-720p.mp4 -an -c:v copy -movflags +faststart "$OUT"
rm -f raw-720p.mp4

echo "----------------------------------------------------------------------"
ffprobe -v error -show_entries format=duration,size -of default=noprint_wrappers=1 "$OUT"
echo "sha256: $(shasum -a 256 "$OUT" | cut -d' ' -f1)"
echo "Re-host $OUT at a stable URL, then set MATERIALS_URL and MATERIALS_SHA256"
echo "in environment/Dockerfile."
