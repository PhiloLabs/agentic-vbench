#!/bin/bash
# Record a suite of races on different tracks, concatenate them into one video, and build the
# hero-scoped ground truth.
#
# The camera follows a single HERO kart (tux) in every race (run_race.sh passes --kart=tux), so
# every scored count is on camera. Eight 3-lap races on eight tracks: the SuperTux AI is fast, so
# eight races clear the 10-minute family minimum with margin and give the cross-race ranking
# enough points (28 pairs) to separate an agent from chance. The rest of the field is varied per
# race for visual variety and real item/bomb contention around the hero.
set -eux
OUT=${1:?outdir}
HERO=${HERO:-tux}
LAPS=${LAPS:-3}
mkdir -p "$OUT"
HERE=$(dirname "$(readlink -f "$0")")
FFX=${FFMPEG:-$(/usr/bin/python3 -c "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())" 2>/dev/null || echo ffmpeg)}
# run_race.sh's video-length assertion needs a real ffprobe; a bare `ffprobe` is often not on PATH
# and silently reported every race as 0s. Resolve one explicitly and export it.
export FFPROBE=${FFPROBE:-$(command -v ffprobe || echo /pkg/ffmpeg/4.2.2/bin/ffprobe)}
export FFMPEG=$FFX

i=0
: > "$OUT/concat.txt"
# Each race: the hero (tux) plus nine other karts — a 10-kart field. Rosters vary per race.
for spec in "hacienda:tux,gnu,adiumy,amanda,beastie,kiki,konqi,nolok,puffy,wilber" \
            "snowmountain:tux,pidgin,konqi,puffy,hexley,wilber,xue,gnu,emule,suzanne" \
            "cornfield_crossing:tux,konqi,nolok,amanda,wilber,puffy,gnu,beastie,pidgin,xue" \
            "lighthouse:tux,emule,gavroche,nolok,suzanne,sara_the_racer,xue,kiki,adiumy,hexley" \
            "gran_paradiso_island:tux,gnu,beastie,kiki,konqi,amanda,puffy,pidgin,wilber,xue" \
            "sandtrack:tux,nolok,hexley,emule,suzanne,gavroche,adiumy,gnu,kiki,konqi" \
            "black_forest:tux,amanda,beastie,puffy,wilber,pidgin,xue,nolok,gnu,hexley" \
            "cocoa_temple:tux,konqi,kiki,adiumy,gavroche,suzanne,emule,sara_the_racer,gnu,amanda"; do
  track=${spec%%:*}; karts=${spec##*:}
  # 900s guard: a 3-lap 10-kart race is ~3-4 min of wall time under llvmpipe software GL; the
  # guard only trips if a track hangs, so one bad track cannot wedge the whole suite.
  timeout 900 bash "$HERE/run_race.sh" "$OUT/race$i" "$track" "$LAPS" "$karts" 3 "$HERO"
  /usr/bin/python3 "$HERE/parse_profile.py" "$OUT/race$i/stk_stdout.log" "$OUT/race$i/gt.json" --expect 10
  test -s "$OUT/race$i/race_raw.mp4" || { echo "race$i produced no video — aborting suite"; exit 7; }
  echo "file 'race$i/race_raw.mp4'" >> "$OUT/concat.txt"
  i=$((i+1))
done

"$FFX" -v error -f concat -safe 0 -i "$OUT/concat.txt" -c:v libx264 -crf 23 -preset veryfast \
       -pix_fmt yuv420p -r 15 "$OUT/race_suite.mp4" -y
SDUR=$("$FFPROBE" -v error -show_entries format=duration -of csv=p=0 "$OUT/race_suite.mp4")
awk -v d="$SDUR" 'BEGIN{exit !(d>600)}' || echo "WARNING: suite is ${SDUR}s, under the 10-minute minimum"

# hero-scoped ground truth (asserts the primary scored field varies across races)
/usr/bin/python3 "$HERE/build_ground_truth.py" "$OUT" "$OUT/ground_truth.json"
echo "SUITE_DONE ${SDUR}s"
