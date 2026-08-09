#!/bin/bash
# Record a SuperTuxKart race under Xvfb with software GL, capturing the X display with ffmpeg
# x11grab. Profile mode drives every kart and prints the exact per-kart result table to stdout,
# so the recorded run is its own ground truth.
#
#   run_race.sh OUTDIR TRACK LAPS "kart1,kart2,..." [DIFFICULTY] [HERO]
#
# The camera follows a single HERO kart (default: the first kart in the list) the entire race:
# STK's profile camera is a chase-cam locked to the player kart, and `--kart=HERO --ai=<rest>`
# makes HERO the (still AI-driven) player. Only HERO's counts are scored downstream, so every
# scored pickup / explosion is on camera by construction — the rest of the field still races
# (competing for boxes, bombing the hero), it is just not the thing being counted.
#
# DIFFICULTY 3 = SuperTux, the strongest AI: it takes better racing lines, uses nitro and
# powerups deliberately and defends position, so the race produces real overtakes, item use and
# explosions. That is what makes the reconstruction non-trivial.
set -eux
OUT=${1:?outdir}; TRACK=${2:-hacienda}; LAPS=${3:-3}
KARTS=${4:-tux,gnu,adiumy,amanda,beastie,kiki}
DIFF=${5:-3}
HERO=${6:-$(echo "$KARTS" | cut -d, -f1)}
# the field minus the hero becomes the AI list; the hero is the player kart the camera tracks
AI=$(echo "$KARTS" | tr ',' '\n' | grep -vx "$HERO" | paste -sd, -)
echo "$KARTS" | tr ',' '\n' | grep -qx "$HERO" || { echo "HERO '$HERO' not in KARTS '$KARTS'"; exit 8; }
STK=${STK:?set STK to the SuperTuxKart 1.5 install dir (contains run_game.sh)}
# Pick a free X display. Reusing a fixed :77 silently broke the second race of a suite:
# the previous Xvfb had not released the lock, the new one died with "Server is already
# active", ffmpeg could not open the display, and the run still reported success with no
# video written.
for n in $(seq 77 99); do
  if [ ! -e "/tmp/.X${n}-lock" ]; then DISPNUM=$n; break; fi
done
: "${DISPNUM:?no free X display in 77..99}"
DISP=":$DISPNUM"
W=1280; H=720
mkdir -p "$OUT"

FF=${FFMPEG:-$(/usr/bin/python3 -c "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())" 2>/dev/null || echo ffmpeg)}

Xvfb $DISP -screen 0 ${W}x${H}x24 -nolisten tcp &
XVFB=$!
trap 'kill $XVFB 2>/dev/null || true' EXIT
sleep 3

# capture first so the grid formation at the start of the race is on tape
DISPLAY=$DISP "$FF" -v error -f x11grab -framerate 15 -video_size ${W}x${H} -i $DISP \
    -c:v libx264 -preset veryfast -crf 23 -pix_fmt yuv420p "$OUT/race_raw.mp4" -y &
CAP=$!

set +e
DISPLAY=$DISP LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe \
  "$STK/run_game.sh" --screensize=${W}x${H} --profile-laps="$LAPS" \
  --track="$TRACK" --numkarts=$(echo "$KARTS" | awk -F, '{print NF}') \
  --difficulty="$DIFF" --kart="$HERO" --ai="$AI" > "$OUT/stk_stdout.log" 2>&1
RC=$?
set -e

sleep 2
kill -INT $CAP 2>/dev/null || true
wait $CAP 2>/dev/null || true
echo "STK_EXIT=$RC"

# A race with no usable video is a failed race, not a quiet one.
test -s "$OUT/race_raw.mp4" || { echo "NO_VIDEO_RECORDED for $TRACK"; exit 5; }
DUR=$("${FFPROBE:-ffprobe}" -v error -show_entries format=duration -of csv=p=0 "$OUT/race_raw.mp4" || echo 0)
awk -v d="$DUR" 'BEGIN{exit !(d>30)}' || { echo "VIDEO_TOO_SHORT ${DUR}s for $TRACK"; exit 6; }
echo "$HERO" > "$OUT/hero.txt"
echo "$TRACK" > "$OUT/track.txt"
echo "RACE_OK $TRACK ${DUR}s hero=$HERO"
grep -c '^\[.*profile: ' "$OUT/stk_stdout.log" || true
