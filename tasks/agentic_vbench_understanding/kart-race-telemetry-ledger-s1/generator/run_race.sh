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

# FRESH OUTPUT DIRECTORY (an argument check, so it runs before the environment ones). Re-running
# into a used directory silently mixes runs: the previous race's stkhome/config.xml is what
# check_hud_config.sh would then assert on, and a previous race_raw.mp4 would survive a failed
# render and be concatenated as if it were this run's.
if [ -e "$OUT" ] && [ -n "$(ls -A "$OUT" 2>/dev/null)" ]; then
  if [ "${AGENTICVBENCH_ALLOW_DIRTY_OUT:-0}" != "1" ]; then
    echo "run_race: output directory is not empty: $OUT"
    echo "  a re-run would mix this race with the previous one (stale config.xml, stale video)."
    echo "  remove it, pick a fresh path, or set AGENTICVBENCH_ALLOW_DIRTY_OUT=1 deliberately."
    exit 14
  fi
  echo "run_race: WARNING reusing non-empty $OUT (AGENTICVBENCH_ALLOW_DIRTY_OUT=1)"
fi

# generator/test_guards.sh uses this to exercise the checks above without rendering. It returns
# after ARGUMENT validation only -- it does not vouch for STK, ffmpeg or the display.
if [ "${AGENTICVBENCH_PRECHECK_ONLY:-0}" = "1" ]; then
  echo "run_race: argument precheck OK for $OUT"
  exit 0
fi
HERE=$(dirname "$(readlink -f "$0")")
STK=${STK:?set STK to the SuperTuxKart 1.5 install dir (contains run_game.sh)}
# Pick a free X display. Reusing a fixed :77 silently broke the second race of a suite:
# the previous Xvfb had not released the lock, the new one died with "Server is already
# active", ffmpeg could not open the display, and the run still reported success with no
# video written.
# A caller running races in parallel passes STK_DISP to guarantee a unique display (the
# check-then-bind loop below races when several starts land at once). Otherwise pick a free one.
if [ -n "${STK_DISP:-}" ]; then
  DISPNUM=$STK_DISP
else
  for n in $(seq 77 99); do
    if [ ! -e "/tmp/.X${n}-lock" ]; then DISPNUM=$n; break; fi
  done
fi
: "${DISPNUM:?no free X display in 77..99}"
DISP=":$DISPNUM"
W=${W:-1280}; H=${H:-720}   # run_suite.sh exports these so the HUD mask is
                            # derived from the SAME size that is rendered

mkdir -p "$OUT"


FF=${FFMPEG:-$(/usr/bin/python3 -c "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())" 2>/dev/null || echo ffmpeg)}
command -v "$FF" >/dev/null 2>&1 || [ -x "$FF" ] || { echo "no usable ffmpeg: '$FF' (resolve FFMPEG before HOME is redirected)"; exit 13; }
FPROBE=${FFPROBE:-$(command -v ffprobe || echo /pkg/ffmpeg/4.2.2/bin/ffprobe)}
[ -x "$FPROBE" ] || { echo "no usable ffprobe: '$FPROBE'"; exit 13; }

# PER-RACE CONFIG HOME. Races run in parallel, so a shared STK config is two problems at once:
# concurrent races race on the config write, and whatever the host happens to have set overrides
# the HUD defaults that generator/hud_mask.py derives the powerup-mask box from. Give each race its
# own fresh HOME/XDG dirs inside its own output directory, so the config STK writes is an artifact
# of that race and can be audited afterwards.
STKHOME="$OUT/stkhome"
mkdir -p "$STKHOME/.config" "$STKHOME/.local/share"
export STKHOME
export HOME="$STKHOME" XDG_CONFIG_HOME="$STKHOME/.config" XDG_DATA_HOME="$STKHOME/.local/share"

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

# The powerup-mask box is derived for STK's DEFAULT indicator placement and size, so assert on
# the config THIS race wrote rather than trusting the environment (see check_hud_config.sh).
bash "$HERE/check_hud_config.sh" "$STKHOME"
DUR=$("$FPROBE" -v error -show_entries format=duration -of csv=p=0 "$OUT/race_raw.mp4" || echo 0)
awk -v d="$DUR" 'BEGIN{exit !(d>30)}' || { echo "VIDEO_TOO_SHORT ${DUR}s for $TRACK"; exit 6; }
echo "$HERO" > "$OUT/hero.txt"
echo "$TRACK" > "$OUT/track.txt"
echo "RACE_OK $TRACK ${DUR}s hero=$HERO"
grep -c '^\[.*profile: ' "$OUT/stk_stdout.log" || true
