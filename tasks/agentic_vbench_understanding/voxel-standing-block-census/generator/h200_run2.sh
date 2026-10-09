#!/bin/bash
# End-to-end Luanti capture, v2.
# ffmpeg starts first and then drops a GO file; the mod's clock starts when it
# sees GO, so the log and the video share t=0. Three screen flashes at
# t=1.0/2.0/4.0 let the alignment be checked afterwards frame by frame.
R=${AVB_LUANTI_ROOT:?set AVB_LUANTI_ROOT to the Luanti build directory (luanti/, games/, world1/)}
SECS=${1:-900}
DISP=:77
cd "$R" || exit 1
mkdir -p "$R/luanti/games"
[ -e "$R/luanti/games/mineclone2" ] || ln -s "$R/games/mineclone2" "$R/luanti/games/mineclone2"

pkill -u "$USER" -f "bin/luanti"   2>/dev/null
pkill -u "$USER" -f "Xvfb $DISP"   2>/dev/null
sleep 2
rm -f "$R/world1/avb_events.log" "$R/world1/GO" "$R/out.mp4"
rm -rf "$R/world1/map.sqlite" "$R/world1/map_meta.txt" "$R/world1/env_meta.txt" "$R/world1/mod_storage.sqlite" "$R/world1/players"

Xvfb $DISP -screen 0 1280x720x24 -nolisten tcp > "$R/xvfb.log" 2>&1 &
XV=$!
sleep 3
[ -S /tmp/.X11-unix/X77 ] || { echo "XVFB FAILED"; cat "$R/xvfb.log"; exit 1; }
echo "xvfb ok"

"$R/luanti/bin/luantiserver" --world "$R/world1" --gameid mineclone2 \
    --config "$R/h200_server.conf" --logfile "$R/server.log" > "$R/server.out" 2>&1 &
SV=$!
sleep 25
grep -q "listening" "$R/server.out" && echo "server ok" || { echo "SERVER BAD"; tail -15 "$R/server.out"; }

export DISPLAY=$DISP LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe
"$R/luanti/bin/luanti" --go --address 127.0.0.1 --port 30099 --name avbcam \
    --config "$R/h200_client.conf" --logfile "$R/client.log" > "$R/client.out" 2>&1 &
CL=$!
sleep 25
ps -p $CL > /dev/null && echo "client alive" || { echo "CLIENT DEAD"; tail -20 "$R/client.out"; }

date +%s.%N > "$R/ffmpeg_start.epoch"
"$R/ff/bin/ffmpeg" -hide_banner -loglevel error -f x11grab -framerate 12 \
    -video_size 1280x720 -i $DISP -t "$SECS" \
    -c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p "$R/out.mp4" -y &
FF=$!
sleep 4
date +%s.%N > "$R/go.epoch"
touch "$R/world1/GO"
echo "GO dropped $(cat "$R/go.epoch")"
wait $FF
echo "ffmpeg rc=$?"

sleep 2
kill -TERM $CL 2>/dev/null; sleep 3; kill -9 $CL 2>/dev/null
kill -TERM $SV 2>/dev/null; sleep 3; kill -9 $SV 2>/dev/null
kill -9 $XV 2>/dev/null
echo "--- events: $(wc -l < "$R/world1/avb_events.log" 2>/dev/null) ---"
head -8 "$R/world1/avb_events.log" 2>/dev/null
echo "--- ffmpeg start $(cat "$R/ffmpeg_start.epoch")  GO $(cat "$R/go.epoch") ---"
echo "--- video ---"
"$R/ff/bin/ffprobe" -v error -show_entries stream=width,height,nb_frames,r_frame_rate,duration -of default=nw=1 "$R/out.mp4" 2>&1
ls -la "$R/out.mp4" 2>/dev/null
echo "--- lua errors ---"
grep -icE 'Runtime error|AsyncErr' "$R/server.out"
