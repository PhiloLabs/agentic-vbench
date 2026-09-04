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
export W=${W:-1280} H=${H:-720}   # render size; the HUD mask is derived from it

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

# HUD POWERUP MASK (this is the step that produces the SHIPPED media).
# STK draws the powerup indicator at the TOP-CENTRE of the viewport, one sprite per held item.
# The box is DERIVED from STK's own drawing code at this render size rather than hard-coded: see
# generator/hud_mask.py, which carries the derivation and a self-test. The row is centred, so it
# grows outward as the held-item count rises and is widest at MAX_POWERUPS=5; a box fitted to a
# narrower row clips the widest one and leaves a visible sliver of the leftmost sprite.
# Every other HUD element is left untouched: ranking column (top-left), timer + lap (top-right),
# minimap (bottom-left), nitro gauge + position (bottom-right).
# Masking the slot is what makes items_collected an OFF-HUD quantity: without it the indicator
# shows the held item type AND count, i.e. a visible per-pickup event the prompt says is absent.
/usr/bin/python3 "$HERE/hud_mask.py" --selftest
eval "$(/usr/bin/python3 "$HERE/hud_mask.py" --width "$W" --height "$H" --shell)"
"$FFX" -v error -i "$OUT/race_suite.mp4" \
       -vf "drawbox=x=${MASK_X}:y=${MASK_Y}:w=${MASK_W}:h=${MASK_H}:color=black@1.0:t=fill" \
       -c:v libx264 -crf 23 -preset veryfast -pix_fmt yuv420p -r 15 -an \
       "$OUT/race.mp4" -y
test -s "$OUT/race.mp4" || { echo "HUD mask pass produced no video — aborting"; exit 9; }

# Check the mask on the FILE THAT SHIPS: measure the black rectangle actually present and require
# it to equal the rectangle hud_mask.py derives. Both directions are checked, so the check is known
# to fire rather than merely to pass. Spotting the sprites themselves would be the more direct test
# and was tried; an alpha-blended sprite sliver is not separable from ordinary scenery at any usable
# threshold (measured -- see NOTES.md), so the box placement is what gets verified.
/usr/bin/python3 "$HERE/verify_mask_box.py" "$OUT/race_suite.mp4" --width "$W" --height "$H" --expect-absent
/usr/bin/python3 "$HERE/verify_mask_box.py" "$OUT/race.mp4"       --width "$W" --height "$H"
echo "MASKED_MEDIA $OUT/race.mp4 sha256=$(sha256sum "$OUT/race.mp4" | cut -d" " -f1)"
SDUR=$("$FFPROBE" -v error -show_entries format=duration -of csv=p=0 "$OUT/race_suite.mp4")
awk -v d="$SDUR" 'BEGIN{exit !(d>600)}' || echo "WARNING: suite is ${SDUR}s, under the 10-minute minimum"

/usr/bin/python3 "$HERE/build_ground_truth.py" "$OUT" "$OUT/ground_truth.json"
echo "SUITE_DONE ${SDUR}s"
