#!/bin/bash
# Turn a captured raw session into the deliverable video + ground truth, in one reproducible step.
#
#   finish_session.sh VERSION_TAG [TASK_DIR]
#
# Reads $D/play_<V>.json + $D/<V>_capture/*.webm and the OFFSET_S printed by capture_mc.py, then:
#   1. composite the authentic HUD (held item tracked per event)
#   2. composite the block-break crack and hurt-flash from the event log
#   3. audit the result for uninformative frames
#   4. build ground truth + oracle and run the anti-shortcut ablations
#
# Every step asserts its input exists, because each of these has silently produced a 0-byte or
# stale output at least once when an earlier stage failed and the chain was run by hand.
set -euo pipefail
V=${1:?version tag}
TASK_DIR=${2:-}
D="${WORK:-/tmp/agenticvbench-mc}/p1-mc"
TOOLS=$(cd "$(dirname "$0")" && pwd)
PLAY=$D/play_$V.json
RAW=$(ls "$D/${V}_capture"/*.webm 2>/dev/null | head -1)

[ -s "$PLAY" ] || { echo "FAIL no ledger $PLAY"; exit 2; }
[ -n "$RAW" ] && [ -s "$RAW" ] || { echo "FAIL no raw capture in $D/${V}_capture"; exit 2; }
OFFSET=$(grep -oE 'OFFSET_S [0-9.]+' "$D/${V}_driver.log" | tail -1 | awk '{print $2}')
[ -n "$OFFSET" ] || { echo "FAIL no OFFSET_S in $D/${V}_driver.log — HUD/FX timing would be wrong"; exit 2; }
echo "raw=$RAW offset=${OFFSET}s events=$(/usr/bin/python3 -c "import json;print(len(json.load(open('$PLAY'))['events']))")"

/usr/bin/python3 "$TOOLS/composite_hud.py" "$RAW" "$PLAY" "$OFFSET" "$D/${V}_hud.mp4"
[ -s "$D/${V}_hud.mp4" ] || { echo "FAIL HUD composite produced nothing"; exit 3; }

/usr/bin/python3 "$TOOLS/fx_overlay.py" "$D/${V}_hud.mp4" "$PLAY" "$OFFSET" "$D/game_$V.mp4"
[ -s "$D/game_$V.mp4" ] || { echo "FAIL FX composite produced nothing"; exit 3; }

/usr/bin/python3 "$TOOLS/frame_audit.py" "$D/game_$V.mp4"

# The ground truth must not contain events the RAW CAPTURE never filmed. The capture wrap can end a
# few seconds before the bot's final events, so an event is only in the video if
# offset + t <= raw_capture_duration. Compute that GO-relative cutoff from the raw webm (the
# composite only trims dead head/tail time, so it never drops an event-bearing second the raw held).
RAWDUR=$(/pkg/ffmpeg/4.2.2/bin/ffprobe -v error -show_entries format=duration -of csv=p=0 "$RAW")
CUTOFF=$(/usr/bin/python3 -c "print(max(0.0, $RAWDUR - $OFFSET - 0.3))")
echo "raw_capture=${RAWDUR}s offset=${OFFSET}s -> GT cutoff ${CUTOFF}s (GO-relative)"
if [ -n "$TASK_DIR" ]; then
  /usr/bin/python3 "$TOOLS/build_p1_gt_v11.py" "$PLAY" "$TASK_DIR" "$OFFSET" "$CUTOFF"
fi

/pkg/ffmpeg/4.2.2/bin/ffprobe -v error -show_entries stream=width,height,r_frame_rate \
  -show_entries format=duration,size -of default=nw=1 "$D/game_$V.mp4"
echo "SHA256 $(sha256sum "$D/game_$V.mp4" | awk '{print $1}')"
echo "FINISH_OK $D/game_$V.mp4"
