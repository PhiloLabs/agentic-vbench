#!/bin/bash
# Record a suite of races on different tracks, concatenate them into one video, and build the
# hero-scoped ground truth.
#
# The camera follows a single HERO kart (tux) in every race (run_race.sh passes --kart=tux), so
# every scored count is on camera. TWELVE 4-lap races on twelve tracks: long enough (~55 min) that
# an agent cannot rely on watching a fraction, and each race yields high pickup/explosion/banana
# counts that must be tallied precisely, then ranked across the suite. Two off-HUD quantities are
# scored (items_collected + skid_time; spinouts/positions are unscored context).
#
# Races are rendered in PARALLEL (each on its own Xvfb display) with a concurrency cap, because a
# sequential 12x4 suite would take ~1 h of software-GL wall time; the machine has plenty of cores.
set -eux
OUT=${1:?outdir}
HERO=${HERO:-tux}
LAPS=${LAPS:-4}
CONC=${CONC:-6}                 # concurrent races
mkdir -p "$OUT"
HERE=$(dirname "$(readlink -f "$0")")
FFX=${FFMPEG:-$(/usr/bin/python3 -c "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())" 2>/dev/null || echo ffmpeg)}
export FFPROBE=${FFPROBE:-$(command -v ffprobe || echo /pkg/ffmpeg/4.2.2/bin/ffprobe)}
export FFMPEG=$FFX

SPECS=(
  "hacienda:tux,gnu,adiumy,amanda,beastie,kiki,konqi,nolok,puffy,wilber"
  "snowmountain:tux,pidgin,konqi,puffy,hexley,wilber,xue,gnu,emule,suzanne"
  "cornfield_crossing:tux,konqi,nolok,amanda,wilber,puffy,gnu,beastie,pidgin,xue"
  "lighthouse:tux,emule,gavroche,nolok,suzanne,sara_the_racer,xue,kiki,adiumy,hexley"
  "gran_paradiso_island:tux,gnu,beastie,kiki,konqi,amanda,puffy,pidgin,wilber,xue"
  "sandtrack:tux,nolok,hexley,emule,suzanne,gavroche,adiumy,gnu,kiki,konqi"
  "olivermath:tux,amanda,beastie,puffy,wilber,pidgin,xue,nolok,gnu,hexley"       # olivermath replaces black_forest: the latter is too heavy for llvmpipe (renders in slow-motion)
  "cocoa_temple:tux,konqi,kiki,adiumy,gavroche,suzanne,emule,sara_the_racer,gnu,amanda"
  "scotland:tux,gavroche,suzanne,sara_the_racer,emule,hexley,kiki,adiumy,beastie,pidgin"
  "fortmagma:tux,konqi,nolok,puffy,wilber,gnu,amanda,beastie,xue,kiki"
  "ravenbridge_mansion:tux,pidgin,hexley,emule,suzanne,gavroche,adiumy,nolok,gnu,puffy"
  "stk_enterprise:tux,amanda,beastie,kiki,konqi,wilber,xue,pidgin,gnu,hexley"
)

# render all races in parallel, capped at CONC, each pinned to its own display 77+i
pids=()
for i in "${!SPECS[@]}"; do
  track=${SPECS[$i]%%:*}; karts=${SPECS[$i]##*:}
  # throttle: wait until fewer than CONC of our jobs are running
  while [ "$(jobs -rp | wc -l)" -ge "$CONC" ]; do wait -n; done
  STK_DISP=$((77+i)) timeout 1200 bash "$HERE/run_race.sh" "$OUT/race$i" "$track" "$LAPS" "$karts" 3 "$HERO" \
      > "$OUT/race$i.log" 2>&1 &
  pids+=($!)
done
wait

# parse + assemble in track order
: > "$OUT/concat.txt"
for i in "${!SPECS[@]}"; do
  /usr/bin/python3 "$HERE/parse_profile.py" "$OUT/race$i/stk_stdout.log" "$OUT/race$i/gt.json" --expect 10
  test -s "$OUT/race$i/race_raw.mp4" || { echo "race$i produced no video — aborting suite"; exit 7; }
  echo "file 'race$i/race_raw.mp4'" >> "$OUT/concat.txt"
done

"$FFX" -v error -f concat -safe 0 -i "$OUT/concat.txt" -c:v libx264 -crf 23 -preset veryfast \
       -pix_fmt yuv420p -r 15 "$OUT/race_suite.mp4" -y
SDUR=$("$FFPROBE" -v error -show_entries format=duration -of csv=p=0 "$OUT/race_suite.mp4")
awk -v d="$SDUR" 'BEGIN{exit !(d>600)}' || echo "WARNING: suite is ${SDUR}s, under the 10-minute minimum"

/usr/bin/python3 "$HERE/build_ground_truth.py" "$OUT" "$OUT/ground_truth.json"
echo "SUITE_DONE ${SDUR}s"
