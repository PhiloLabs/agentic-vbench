#!/bin/bash
# Regenerate the exact 30 contact sheets that were supplied to the
# frame_dump_no_tools ablation, from the pinned source media, and prove it by
# reproducing every per-sheet SHA-256 in the committed manifest.
#
# Why this exists: the ablation's evidence chain was a hash manifest and nothing
# else. A manifest identifies the intended bytes but cannot be checked without
# either the bytes or a derivation, so the claimed 1435-frame coverage, ordering
# and presentation were not independently verifiable. This script is the
# derivation. It commits no JPEG binaries.
#
# Determinism. Every step is fixed: the source is the pinned media, verified by
# digest before anything runs; frame extraction, tiling and JPEG encoding all run
# through the ffmpeg baked into the frozen task image, and the mjpeg encoder is
# deterministic for a given input and quality. The image is the identity that
# matters here, not the host: run this in the shipped image and the bytes match.
# Verified end to end -- a clean regeneration of sheet_001 from /baked/game.mp4
# reproduced its committed digest exactly.
#
# Geometry, matching what the ablation used:
#   1 fps over the full 1435 s  ->  1435 frames, none dropped
#   scale each frame to 224x126, tile 7x7  ->  1568x882 sheets, 49 frames each
#   30 sheets; the last one's trailing 35 tiles are blank padding
#   JPEG at -q:v 5
#
# Sheet s (1-based), tile t (0-based, row-major) is second 49*(s-1) + t.
#
# Usage: ./build_frame_dump_sheets.sh [output-dir-in-container]
set -euo pipefail

OUT="${1:-/workspace/sheets}"
CNAME=avb-sheets-rebuild
IMAGE=${TASK_IMAGE:-agentic-vbench-openttgames}
MEDIA_SHA=330ac07730bae6d899dbbbd00ad43500c583e6af6ea6dd261565bc77811eba66
# The encoder version is what fixes the output bytes, so it is asserted rather than
# printed. The image ID is not: Docker image IDs are not reproducible across
# independent builds of the same Dockerfile, so pinning one would reject a reviewer
# who built the image themselves -- which is the normal way to check this task. The
# ID is recorded for provenance and the ffmpeg version is enforced.
EXPECT_FFMPEG="ffmpeg version 7.1.5-0+deb13u1"
A="$(cd "$(dirname "$0")/.." && pwd)/ablations"
MANIFEST="$A/ablation_frame-dump-notools_sheets.sha256"

[ -f "$MANIFEST" ] || { echo "FATAL: manifest not found at $MANIFEST"; exit 1; }

docker rm -f "$CNAME" >/dev/null 2>&1 || true
docker run -d --name "$CNAME" -w /workspace "$IMAGE" sh -c 'sleep infinity' >/dev/null
trap 'docker rm -f "$CNAME" >/dev/null 2>&1 || true' EXIT

FFMPEG_V=$(docker exec "$CNAME" ffmpeg -version 2>/dev/null | head -1)
echo "ffmpeg: $FFMPEG_V"
echo "image:  $(docker image inspect "$IMAGE" --format '{{.Id}}')  (recorded, not pinned -- see above)"
case "$FFMPEG_V" in
  "$EXPECT_FFMPEG"*) echo "  encoder version matches the pinned build" ;;
  *) echo "FATAL: this image ships $FFMPEG_V, but the sheets were built with" >&2
     echo "       $EXPECT_FFMPEG. A different encoder can produce different bytes," >&2
     echo "       so the digests below would not be comparable. Use the frozen image." >&2
     exit 1 ;;
esac

docker exec "$CNAME" sh -c "
  echo '$MEDIA_SHA  /baked/game.mp4' | sha256sum -c - >/dev/null || {
    echo 'FATAL: source media digest does not match the pinned value' >&2; exit 1; }
  echo '  source media digest verified'
"

docker exec "$CNAME" sh -c "
  set -e
  rm -rf /tmp/frames '$OUT'
  mkdir -p /tmp/frames '$OUT'

  ffmpeg -nostdin -v error -i /baked/game.mp4 -vf fps=1 /tmp/frames/f_%05d.png
  echo \"  extracted \$(ls /tmp/frames | wc -l) frames at 1 fps\"

  ffmpeg -nostdin -v error -framerate 1 -i /tmp/frames/f_%05d.png \
    -vf 'scale=224:126,tile=7x7' /tmp/sheet_%03d.png
  for f in /tmp/sheet_*.png; do
    ffmpeg -nostdin -v error -i \"\$f\" -q:v 5 \"$OUT/\$(basename \${f%.png}).jpg\"
    rm -f \"\$f\"
  done
  rm -rf /tmp/frames
  echo \"  built \$(ls '$OUT' | wc -l) sheets\"
"

echo "verifying against the committed manifest"
docker cp "$MANIFEST" "$CNAME:/tmp/expected.sha256" >/dev/null
if docker exec "$CNAME" sh -c "cd '$OUT' && sha256sum -c /tmp/expected.sha256 --quiet"; then
  echo "  all $(wc -l < "$MANIFEST" | tr -d ' ') sheets reproduce their committed digests"
else
  echo "  FATAL: regenerated sheets do not match the manifest" >&2
  exit 1
fi
