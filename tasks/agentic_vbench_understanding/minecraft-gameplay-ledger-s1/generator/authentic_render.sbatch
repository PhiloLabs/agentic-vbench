#!/bin/bash
#SBATCH --job-name=avb_mc_authentic
#SBATCH --nodes=1
#SBATCH --nodelist=galaxy
#SBATCH --cpus-per-task=32
#SBATCH --mem=16000M
#SBATCH --partition=zhanglab.p
#SBATCH --time=2:00:00
#SBATCH --output=slurm-%j.out   # written to the submit directory
#
# Authentic Minecraft render: a REAL Minecraft 1.16.5 client joins the Paper server as a
# spectator locked to the mineflayer bot, so the video gets the effects the headless JS
# renderer cannot draw — block-break cracks, entity hurt flash, hand swing, particles, sound.
# The bot logic (bot_play8.js) is reused UNCHANGED; only the renderer differs.
#
# CPU, not GPU, on purpose: LWJGL/GLFW makes its GL context through GLX on X11, and Xvfb only
# offers SOFTWARE GLX, so an allocated GPU would sit idle. llvmpipe is multithreaded, so what
# actually decides the frame rate is dedicated cores — hence 32 CPUs and no --gres.
# galaxy is required (not just preferred): the SSD is node-local there and the
# Paper server the client must reach runs on this host.
set -x
SSD="${WORK:-/tmp/agenticvbench-mc}"   # set WORK to a fast node-local SSD dir
MC=$SSD/mc-client
SRV=$SSD/p1-mc-server
OUT=$SSD/mc-authentic
TOOLS="${TOOLS:-$HOME/text-dna/agenticvbench-claude/generator}"
mkdir -p "$OUT"

echo "HOST=$(hostname) CPUS=${SLURM_CPUS_PER_TASK:-?} LOAD=$(cut -d' ' -f1-3 /proc/loadavg)"

# ---- preflight: fail fast rather than burn the allocation -------------------------------
[ -s "$MC/bin/client.jar" ]   || { echo "PREFLIGHT_FAIL no client.jar";   exit 3; }
[ -s "$MC/classpath.txt" ]    || { echo "PREFLIGHT_FAIL no classpath";    exit 3; }
[ -s "$SRV/paper.jar" ]       || { echo "PREFLIGHT_FAIL no paper.jar";    exit 3; }
command -v Xvfb >/dev/null    || { echo "PREFLIGHT_FAIL no Xvfb";         exit 3; }
FF=${FFMPEG:-$(/usr/bin/python3 -c "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())" 2>/dev/null || echo ffmpeg)}
[ -x "$FF" ] || command -v "$FF" >/dev/null || { echo "PREFLIGHT_FAIL no ffmpeg"; exit 3; }

# ---- server ----------------------------------------------------------------------------
rm -f "$SRV"/world*/session.lock
cd "$SRV" && /usr/bin/java -Xmx3G -Xms1G -jar paper.jar nogui > "$OUT/server.log" 2>&1 &
SRVPID=$!
for i in $(seq 1 60); do grep -q 'Done (' "$OUT/server.log" && break; sleep 2; done
grep -q 'Done (' "$OUT/server.log" || { echo "SERVER_NEVER_READY"; kill $SRVPID; exit 4; }
echo "SERVER_READY"

# ---- display -----------------------------------------------------------------------------
for n in $(seq 80 99); do [ ! -e /tmp/.X${n}-lock ] && D=$n && break; done
: "${D:?no free X display}"
Xvfb :$D -screen 0 1280x720x24 -nolisten tcp & XVFB=$!
sleep 3

# ---- the bot (same logic as the JS-rendered sessions) -----------------------------------
cd "$TOOLS"
node bot_play8.js "$OUT/play.json" "$OUT/GO" "$OUT/DONE" > "$OUT/bot.log" 2>&1 &
BOT=$!
sleep 25
kill -0 $BOT 2>/dev/null || { echo "BOT_DIED_EARLY"; tail -5 "$OUT/bot.log"; kill $SRVPID $XVFB; exit 5; }

# ---- the real client, as a spectator camera ---------------------------------------------
CP=$(cat "$MC/classpath.txt")
DISPLAY=:$D LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe MESA_GL_VERSION_OVERRIDE=3.3 \
  /usr/bin/java -Xmx3G -cp "$CP" -Djava.library.path="$MC/natives" \
  net.minecraft.client.main.Main --username Camera --version 1.16.5 \
  --gameDir "$MC" --assetsDir "$MC/assets" --assetIndex 1.16 \
  --uuid 00000000000000000000000000000001 --accessToken 0 --userType legacy \
  --width 1280 --height 720 --server 127.0.0.1 --port 25577 > "$OUT/client.log" 2>&1 &
CLIENT=$!

# wait for the client to actually appear on the server before recording anything
JOINED=no
for i in $(seq 1 90); do
  grep -qiE 'Camera.*(joined the game|logged in)' "$OUT/server.log" && { JOINED=yes; break; }
  kill -0 $CLIENT 2>/dev/null || break
  sleep 4
done
echo "CLIENT_JOINED=$JOINED after $((i*4))s"
if [ "$JOINED" != yes ]; then
  echo "CLIENT_NEVER_JOINED — see client.log; likely still loading under software GL"
  tail -20 "$OUT/client.log"; kill $CLIENT $BOT $SRVPID $XVFB 2>/dev/null; exit 6
fi

# lock the camera to the bot's point of view (server-side; no client mod, no keypresses)
node -e '
const mineflayer=require("mineflayer");
const b=mineflayer.createBot({host:"localhost",port:25577,username:"Director",version:"1.16.5",auth:"offline"});
b.once("spawn",async()=>{const s=ms=>new Promise(r=>setTimeout(r,ms));
  b.chat("/gamemode spectator Camera"); await s(800);
  b.chat("/spectate Builder Camera");  await s(800);
  console.log("SPECTATE_SENT"); process.exit(0);});
' >> "$OUT/director.log" 2>&1 || echo "director failed (Director may need op)"

# ---- record, then start the session ------------------------------------------------------
DISPLAY=:$D "$FF" -v error -f x11grab -framerate 15 -video_size 1280x720 -i :$D \
  -c:v libx264 -preset veryfast -crf 23 -pix_fmt yuv420p "$OUT/authentic_raw.mp4" -y & CAP=$!
sleep 3
touch "$OUT/GO"

for i in $(seq 1 450); do [ -f "$OUT/DONE" ] && break; sleep 4; done
sleep 5
kill -INT $CAP 2>/dev/null; wait $CAP 2>/dev/null
kill $CLIENT $BOT 2>/dev/null
sleep 2
kill $SRVPID $XVFB 2>/dev/null

test -s "$OUT/authentic_raw.mp4" && echo "AUTHENTIC_OK $(du -h "$OUT/authentic_raw.mp4" | cut -f1)" \
  || echo "NO_VIDEO_RECORDED"
