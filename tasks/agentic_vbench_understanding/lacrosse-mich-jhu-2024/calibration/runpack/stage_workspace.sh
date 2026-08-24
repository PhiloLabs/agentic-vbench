#!/bin/bash
# Stage a fresh, clean calibration workspace for a given harness.
# Usage: ./stage_workspace.sh codex|gemini
# Anti-cheat properties enforced here:
#  - workspace lives OUTSIDE the project repo (no GT/answer key reachable)
#  - only the four agent-visible materials are copied
#  - media hash verified against the pinned SHA-256
#  - guard scan proves no key/GT files present
set -euo pipefail
H="${1:?usage: stage_workspace.sh codex|gemini}"
SRC="$(cd "$(dirname "$0")/../.." && pwd)"          # task folder
W="/private/tmp/avb_calib_${H}"

rm -rf "$W"; mkdir -p "$W/output"
cp "$SRC/materials/game.mp4"        "$W/game.mp4"
cp "$SRC/steps/solve/instruction.md" "$W/instruction.md"
cp "$SRC/environment/roster.json"    "$W/roster.json"
cp "$SRC/environment/schema.json"    "$W/schema.json"

# harness-specific rules file (both read their conventional filename)
cp "$(dirname "$0")/AGENTS.md" "$W/AGENTS.md"
cp "$(dirname "$0")/AGENTS.md" "$W/GEMINI.md"

# verify media integrity against the pinned hash
PIN=$(cut -d' ' -f1 "$SRC/materials/game.mp4.sha256")
GOT=$(shasum -a 256 "$W/game.mp4" | cut -d' ' -f1)
[ "$PIN" = "$GOT" ] || { echo "FATAL: game.mp4 hash mismatch"; exit 1; }

# guard: prove the workspace is key-free
if find "$W" -iname "*answer*" -o -iname "*ground_truth*" -o -iname "*key*" \
     -o -iname "*verify*" | grep -q .; then
  echo "FATAL: forbidden file staged"; exit 1
fi

echo "staged: $W"
ls -la "$W"
echo "media sha256 OK: $GOT"
