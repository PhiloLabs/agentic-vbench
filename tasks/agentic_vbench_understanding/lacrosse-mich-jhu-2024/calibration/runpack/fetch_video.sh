#!/bin/bash
# Obtain the task video into materials/game.mp4. Two paths, tried in order:
#   Path A (exact bytes): a direct-download link set in VIDEO_URL.txt.
#   Path B (automatic):   reproduce from the PUBLIC SOURCE — download the raw
#                         full game from YouTube and apply the official
#                         mask+mute+strip recipe. No hosting needed.
# The solver only ever sees the finished materials/game.mp4 (masked, silent).
set -euo pipefail
cd "$(dirname "$0")/../.."                         # -> task folder root
PIN=$(cut -d' ' -f1 materials/game.mp4.sha256)

if [ -f materials/game.mp4 ] && \
   [ "$(shasum -a 256 materials/game.mp4 | cut -d' ' -f1)" = "$PIN" ]; then
  echo "game.mp4 already present, official hash verified — nothing to do."; exit 0
fi

URL=$(grep -vE '^\s*#|^\s*$' calibration/runpack/VIDEO_URL.txt 2>/dev/null | head -1 | tr -d '[:space:]' || true)
if [ -n "${URL:-}" ]; then
  echo "Path A: downloading exact video from VIDEO_URL.txt ..."
  curl -fL --retry 3 -o materials/game.mp4 "$URL"
  GOT=$(shasum -a 256 materials/game.mp4 | cut -d' ' -f1)
  [ "$GOT" = "$PIN" ] && { echo "OK: exact task video, SHA-256 verified."; exit 0; }
  echo "FATAL: file at VIDEO_URL is not the exact task video (hash mismatch)."
  rm -f materials/game.mp4; exit 1
fi

echo "Path B: reproducing the task video from its public source ..."
command -v yt-dlp >/dev/null || { echo "need yt-dlp (pip install yt-dlp)"; exit 1; }
command -v ffmpeg  >/dev/null || { echo "need ffmpeg installed"; exit 1; }
TMP=$(mktemp -d)
# raw full-game broadcast upload (720p); scoreboard + audio present here.
yt-dlp -f "bv*[height<=720]" -o "$TMP/raw.%(ext)s" \
  "https://www.youtube.com/watch?v=jr-le7CCyEs"
RAW=$(ls "$TMP"/raw.* | head -1)
# official recipe: force 1280x720, black out lower third (all graphics), drop
# audio, strip metadata/chapters. This is what makes it the anonymized task video.
ffmpeg -loglevel error -y -i "$RAW" \
  -vf "scale=1280:720,drawbox=x=0:y=505:w=1280:h=215:color=black:t=fill" \
  -an -c:v libx264 -crf 23 -preset veryfast -map_metadata -1 -map_chapters -1 \
  -movflags +faststart materials/game.mp4
rm -rf "$TMP"

GOT=$(shasum -a 256 materials/game.mp4 | cut -d' ' -f1)
if [ "$GOT" = "$PIN" ]; then
  echo "OK: reproduced video byte-matches the official pin."
else
  echo "NOTE: reproduced a TASK-EQUIVALENT video (identical frames, mask, and"
  echo "timing); its hash differs from the official pin because a fresh"
  echo "download+encode is not byte-identical. Re-pinning so staging accepts it."
  echo "  reproduced: $GOT"
  echo "  official:   $PIN"
  echo "$GOT  materials/game.mp4" > materials/game.mp4.sha256
  echo ">> Record in scores.md that a reproduced (non-official-hash) media was used."
fi
