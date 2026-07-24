#!/bin/bash
# Record a suite of races on different tracks and concatenate them into one video.
# Four 4-lap races. The SuperTux AI is fast — three 3-lap races came to only 7.7 min — so the
# suite is sized to clear the 10-minute family minimum with margin. Each race is its own
# ground-truth block and the track change is a natural segment boundary for the agent.
set -eux
OUT=${1:?outdir}
mkdir -p "$OUT"
HERE=$(dirname "$(readlink -f "$0")")
FFX=${FFMPEG:-$(/usr/bin/python3 -c "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())" 2>/dev/null || echo ffmpeg)}

i=0
: > "$OUT/concat.txt"
# 10 karts per race across 5 tracks. Bigger fields are both harder (ten karts' pickups to
# follow) and statistically tighter: tau over 45 pairs per field instead of 15 shrinks the
# noise, so one run can actually separate an agent from chance.
for spec in "hacienda:tux,gnu,adiumy,amanda,beastie,kiki,konqi,nolok,puffy,wilber" \
            "snowmountain:pidgin,konqi,puffy,hexley,wilber,xue,tux,gnu,emule,suzanne" \
            "lighthouse:emule,gavroche,nolok,suzanne,sara_the_racer,sara_the_wizard,xue,kiki,adiumy,hexley" \
            "cornfield_crossing:tux,konqi,nolok,amanda,wilber,puffy,gnu,beastie,pidgin,xue" \
            "scotland:gavroche,suzanne,sara_the_racer,emule,hexley,kiki,adiumy,amanda,beastie,sara_the_wizard"; do
  track=${spec%%:*}; karts=${spec##*:}
  bash "$HERE/run_race.sh" "$OUT/race$i" "$track" 4 "$karts" 3
  /usr/bin/python3 "$HERE/parse_profile.py" "$OUT/race$i/stk_stdout.log" "$OUT/race$i/gt.json" --expect 10
  test -s "$OUT/race$i/race_raw.mp4" || { echo "race$i produced no video — aborting suite"; exit 7; }
  echo "file 'race$i/race_raw.mp4'" >> "$OUT/concat.txt"
  i=$((i+1))
done

"$FFX" -v error -f concat -safe 0 -i "$OUT/concat.txt" -c:v libx264 -crf 23 -preset veryfast \
       -pix_fmt yuv420p -r 15 "$OUT/race_suite.mp4" -y
SDUR=$(${FFPROBE:-ffprobe} -v error -show_entries format=duration -of csv=p=0 "$OUT/race_suite.mp4")
awk -v d="$SDUR" 'BEGIN{exit !(d>600)}' || echo "WARNING: suite is ${SDUR}s, under the 10-minute minimum"
echo "SUITE_DONE ${SDUR}s"
