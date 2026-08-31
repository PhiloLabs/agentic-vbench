#!/bin/bash
# Record an AUTHENTIC Minecraft session: the real 1.20.4 client renders the world while the same
# mineflayer bot that drives the headless path plays in it, with the client locked to the bot's
# point of view by /spectate. Nothing is composited — cracks, hurt flashes, hand swing, particles
# and sound are the game's own.
#
#   authentic_session.sh OUTDIR [PHASES]
#
# Why this shape (each point cost a failed attempt):
#   * 1.20.4, not 1.16.5 — `--server` never auto-connected in 1.16.5; quickPlay arrived in 1.20.
#   * options.txt with onboardAccessibility:false — the 1.20 first-launch accessibility screen
#     blocks quickPlay, and it was the reason the client sat on a four-button dialog.
#   * JDK 21 from $HOME — 1.20 needs Java 17+, this host only has 8 and 11.
#   * NO_VIEWER=1 — the bot's own prismarine-viewer is pointless here and just burns CPU.
#   * the port is checked before launch, because a stale server silently ate an earlier run.
#   * the Camera is NEVER op'd and chat is hidden. Paper broadcasts "Builder issued server command:
#     /setblock ... minecraft:oak_planks" to every op, so an op'd camera prints the exact ground
#     truth on screen -- a total answer leak in the graded footage.
#   * the Camera is put in spectator the instant it joins, and the world spawn is forced to open
#     ground. It previously spent ~4 s in survival inside solid stone at the default spawn,
#     suffocated, and the whole recording was the death screen; `/spectate` then failed with
#     "Attempt to teleport removed player Camera restricted" because a dead player cannot be
#     teleported. The old script printed SPECTATE_LOCKED unconditionally and never noticed.
#   * ops.json is written BEFORE the server starts. A fresh Paper server has `ops: []`, and an
#     unprivileged player gets *"Unknown command"* for /setblock, /summon and /locate -- Brigadier
#     hides commands you may not run. That looks exactly like a version incompatibility and cost a
#     whole session (0 events recorded) before `probe_1204.js` isolated it.
set -eux
OUT=${1:?outdir}
PHASES=${2:-start,forest,build_village}
MC="${WORK:-/tmp/agenticvbench-mc}/mc-client-1204"
SRV="${WORK:-/tmp/agenticvbench-mc}/p1-mc-server-1204"
TOOLS="${TOOLS:-$HOME/text-dna/agenticvbench-claude/generator}"
J=$HOME/jdk-21.0.11+10/bin/java
PORT=25590
mkdir -p "$OUT"
FF=${FFMPEG:-$(/usr/bin/python3 -c "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())" 2>/dev/null || echo ffmpeg)}

[ -s "$MC/bin/client.jar" ] || { echo "PREFLIGHT_FAIL no 1.20.4 client"; exit 3; }
[ -x "$J" ]                 || { echo "PREFLIGHT_FAIL no JDK 21";       exit 3; }
grep -q onboardAccessibility "$MC/options.txt" || { echo "PREFLIGHT_FAIL options.txt missing the onboarding opt-out"; exit 3; }
/usr/bin/python3 "$TOOLS/make_ops.py" "$SRV" Builder Director Follower   # NOT Camera -- op leaks command echo
grep -q '"name": "Builder"' "$SRV/ops.json" || { echo "PREFLIGHT_FAIL Builder not op'd"; exit 3; }
grep -q '"name": "Camera"'  "$SRV/ops.json" && { echo "PREFLIGHT_FAIL Camera must NOT be op (chat leak)"; exit 3; }
# hide chat in the client too, belt and braces against any broadcast we did not anticipate
/usr/bin/python3 - "$MC/options.txt" <<'EOP'
import re, sys
p = sys.argv[1]; t = open(p).read()
t = re.sub(r'^chatVisibility:\d+$', 'chatVisibility:2', t, flags=re.M)   # 2 = hidden
if 'chatVisibility' not in t: t += 'chatVisibility:2\n'
open(p, 'w').write(t)
print('options.txt chatVisibility ->', re.search(r'chatVisibility:\d+', t).group(0))
EOP
grep -q '^chatVisibility:2$' "$MC/options.txt" || { echo "PREFLIGHT_FAIL chat not hidden"; exit 3; }

# Kill ONLY a stale server for THIS world. Both the 1.16.5 and 1.20.4 servers have the identical
# command line (`java -jar paper.jar nogui`), so match on the process's cwd -- a blanket
# `grep paper.jar | kill` would take down the headless render running in parallel.
for pid in $(ps -u "$USER" -o pid,cmd | grep 'paper.jar' | grep -v grep | awk '{print $1}'); do
  [ "$(readlink -f /proc/$pid/cwd 2>/dev/null)" = "$(readlink -f "$SRV")" ] && kill $pid || true
done
sleep 4
for n in $(seq 60 79); do [ ! -e /tmp/.X${n}-lock ] && D=$n && break; done
: "${D:?no free X display}"
Xvfb :$D -screen 0 1280x720x24 -nolisten tcp & XVFB=$!
sleep 3

rm -f "$SRV"/world*/session.lock
# Drop the Camera's saved playerdata. /setworldspawn only places players who have none, so a stale
# .dat from an earlier run kept respawning the camera at its last position -- which was inside stone,
# giving a uniform grey view that is indistinguishable from a loading screen.
CAM_UUID=$(/usr/bin/python3 -c "
import hashlib, uuid
h = bytearray(hashlib.md5(b'OfflinePlayer:Camera').digest()); h[6] = (h[6] & 0x0F) | 0x30; h[8] = (h[8] & 0x3F) | 0x80
print(uuid.UUID(bytes=bytes(h)))")
rm -f "$SRV"/world*/playerdata/${CAM_UUID}.dat "$SRV"/world*/playerdata/${CAM_UUID}.dat_old
echo "cleared Camera playerdata ($CAM_UUID)"
(cd "$SRV" && "$J" -Xmx3G -jar paper.jar nogui > "$OUT/server.log" 2>&1) & SRVPID=$!
for i in $(seq 1 90); do grep -q 'Done (' "$OUT/server.log" && break; sleep 2; done
(exec 3<>/dev/tcp/127.0.0.1/$PORT) 2>/dev/null || { echo "SERVER_NOT_LISTENING"; kill $SRVPID $XVFB; exit 4; }
echo SERVER_READY

# the gameplay bot — same file as the headless path, different version/port, viewer off
cd "$TOOLS"
# P1_HOSTILES/P1_EXTRA_BUILDS: the real client renders every mob and we want the richer showcase,
# so the authentic path fights creepers/zombies/skeletons/spiders and builds a desert temple.
MC_VERSION=1.20.4 MC_PORT=$PORT NO_VIEWER=1 P1_HOSTILES=1 P1_EXTRA_BUILDS=1 P1_CAMERA_FOLLOW=1 P1_PHASES="$PHASES" \
  node bot_play8.js "$OUT/play.json" "$OUT/GO" "$OUT/DONE" > "$OUT/bot.log" 2>&1 & BOT=$!
for i in $(seq 1 40); do grep -qi 'Builder joined' "$OUT/server.log" && break; sleep 2; done
grep -qi 'Builder joined' "$OUT/server.log" || { echo "BOT_NEVER_JOINED"; tail -5 "$OUT/bot.log"; kill $BOT $SRVPID $XVFB; exit 5; }
echo BOT_JOINED

# Prepare the world BEFORE the client connects: no command echo (that was the answer leak), daylight,
# and a world spawn ON THE BOT so the camera joins next to the action.
#
# The world spawn is aimed with `/execute at Builder run setworldspawn ~ ~1 ~` rather than by reading
# the Builder entity from the Director bot. The bot travels hundreds of blocks to reach a biome, so it
# sits outside the Director's entity-tracking range and `players.Builder.entity` is undefined -- which
# silently fell back to the Director's own spot and left the world spawn ~330 blocks away. The camera
# then logged in there, and /spectate teleported it into chunks the client had never downloaded, so it
# rendered dark empty space (brightness 24, 6 distinct colours) even though the server reported
# daytime and a clean /spectate. Server-side relative coordinates avoid entity tracking entirely.
#
# Keep the embedded JS free of prose: it lives inside a single-quoted shell string, so one apostrophe
# in a comment ("the Director's spot") silently ends the string and node dies on a syntax error.
node -e '
const mineflayer=require("mineflayer");
const b=mineflayer.createBot({host:"localhost",port:'"$PORT"',username:"Director",version:"1.20.4",auth:"offline"});
b.once("spawn",async()=>{const s=ms=>new Promise(r=>setTimeout(r,ms));
  // sendCommandFeedback stays ON: the gameplay bot reads /locate biome output to travel to biomes,
  // and turning it off silently broke that on every Java render (all traveled biomes were missed).
  // The graded-video leak is prevented where it actually shows up -- the Camera renders NO chat
  // (chatVisibility:2) and is not op -- plus logAdminCommands off stops the op broadcast.
  b.chat("/gamerule sendCommandFeedback true");  await s(400);
  b.chat("/gamerule logAdminCommands false");    await s(400);
  b.chat("/gamerule doDaylightCycle false");     await s(300);
  b.chat("/time set day"); await s(300); b.chat("/weather clear"); await s(300);
  b.chat("/execute at Builder run setworldspawn ~ ~1 ~"); await s(700);
  console.log("WORLD_PREPARED at-Builder"); process.exit(0);});
b.on("error",e=>{console.log("DIRECTOR_ERR",e.message);process.exit(1);});' >> "$OUT/director.log" 2>&1 || true
grep -q WORLD_PREPARED "$OUT/director.log" || { echo "PREFLIGHT_FAIL world not prepared"; kill $BOT $SRVPID $XVFB; exit 7; }
tail -1 "$OUT/director.log"

CP=$(cat "$MC/classpath.txt"); AIDX=$(cut -d= -f2 "$MC/asset_index.txt")
DISPLAY=:$D LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe MESA_GL_VERSION_OVERRIDE=3.3 \
  "$J" -Xmx3G -cp "$CP" -Djava.library.path="$MC/natives" net.minecraft.client.main.Main \
  --username Camera --version 1.20.4 --gameDir "$MC" --assetsDir "$MC/assets" --assetIndex "$AIDX" \
  --uuid 00000000000000000000000000000001 --accessToken 0 --userType legacy \
  --width 1280 --height 720 --quickPlayMultiplayer 127.0.0.1:$PORT > "$OUT/client.log" 2>&1 & CLIENT=$!
for i in $(seq 1 75); do grep -qi 'Camera joined' "$OUT/server.log" && break; sleep 4; done
grep -qi 'Camera joined' "$OUT/server.log" || { echo "CLIENT_NEVER_JOINED"; tail -10 "$OUT/client.log"; kill $CLIENT $BOT $SRVPID $XVFB; exit 6; }
echo CLIENT_JOINED

# Lock the camera to the bot, and CONFIRM it from the server's own complaint stream.
#
# Two things make this awkward and both were learned the hard way. (1) For a few seconds after
# "Camera joined the game" the player entity is still 'removed' server-side, and /spectate answers
# "Attempt to teleport removed player Camera restricted" -- so a single early attempt silently does
# nothing. (2) A spectator is NOT transmitted to other clients as an entity, so a Director bot can
# never see the camera's position; confirming the follow by comparing coordinates is impossible, and
# an earlier watcher that tried spun until it gave up. Since sendCommandFeedback/logAdminCommands are
# off (they leaked the ledger into chat), there is no success message either.
#
# What IS observable is the failure: mark the log, issue the commands, and read only the new bytes.
# No complaint after the final attempt means it took.
spectate_once() {
  node -e '
const mineflayer=require("mineflayer");
const b=mineflayer.createBot({host:"localhost",port:'"$PORT"',username:"Director",version:"1.20.4",auth:"offline"});
const s=ms=>new Promise(r=>setTimeout(r,ms));
b.once("spawn",async()=>{ b.chat("/gamemode spectator Camera"); await s(600);
  // Seed the camera onto the bot. Continuous following is done by the BOT itself (/tp Camera Builder
  // on a loop, P1_CAMERA_FOLLOW): /spectate froze on teleport, so it is not used.
  b.chat("/tp Camera Builder"); await s(900); process.exit(0);});
b.on("error",()=>process.exit(1));' >> "$OUT/spectate.log" 2>&1 || true
}
SPECTATE_OK=0
for attempt in 1 2 3 4 5; do
  sleep 5                                  # let the login finish before poking it
  MARK=$(wc -c < "$OUT/server.log")
  spectate_once
  sleep 2
  if ! tail -c +$((MARK + 1)) "$OUT/server.log" | grep -q 'removed player'; then
    SPECTATE_OK=1; echo "SPECTATE_OK attempt=$attempt"; break
  fi
  echo "spectate-retry $attempt (server still calls Camera a removed player)"
done
[ "$SPECTATE_OK" = "1" ] || { echo "SPECTATE_FAILED after 5 attempts"
  grep -i 'removed player\|died\|suffocat' "$OUT/server.log" | tail -3
  kill $CLIENT $BOT $SRVPID $XVFB; exit 8; }

# (camera following is handled inside the bot via P1_CAMERA_FOLLOW — see bot_play8.js)

# Wait for the client to actually be showing the WORLD before recording anything. A fixed sleep is
# not enough: under software GL, at a relocated world spawn, 25 s still left the client on the flat
# loading-terrain screen (dominant colour share 0.66 over 12 quantised colours). screen_state.py
# distinguishes world / ui / flat and is calibrated against a death screen and a loading screen that
# each fooled a cruder check.
WORLD_READY=0
for i in $(seq 1 40); do
  sleep 6
  DISPLAY=:$D "$FF" -v error -f x11grab -video_size 1280x720 -i :$D -frames:v 1 "$OUT/precheck.png" -y
  if STATE=$(/usr/bin/python3 "$TOOLS/screen_state.py" "$OUT/precheck.png"); then
    echo "WORLD_READY after $((i*6))s — $STATE"; WORLD_READY=1; break
  fi
  [ $((i % 5)) = 0 ] && echo "  waiting for the world ($((i*6))s): $STATE"
done
# `flat` means in-world but a dull view (fog, or the camera briefly inside terrain) -- that is not a
# broken client, and gating on it deadlocks: the interesting view only exists after GO, which comes
# after this check. Only a `ui` screen (menu, death) is fatal.
if [ "$WORLD_READY" != "1" ]; then
  case "$STATE" in
    ui*) echo "WORLD_NEVER_RENDERED — client is on a UI screen: $STATE"
         grep -i 'removed player\|died\|suffocat' "$OUT/server.log" | tail -3
         kill $CLIENT $BOT $SRVPID $XVFB; exit 10 ;;
    *)   echo "WARN proceeding on a dull-but-live view: $STATE" ;;
  esac
fi

DISPLAY=:$D "$FF" -v error -f x11grab -framerate 15 -video_size 1280x720 -i :$D \
  -c:v libx264 -preset veryfast -crf 23 -pix_fmt yuv420p "$OUT/authentic.mp4" -y & CAP=$!
sleep 2
touch "$OUT/GO"                            # start the session

for i in $(seq 1 450); do [ -f "$OUT/DONE" ] && break; sleep 4; done
sleep 4
kill -INT $CAP 2>/dev/null || true; wait $CAP 2>/dev/null || true
kill $CLIENT $BOT 2>/dev/null || true; sleep 2; kill $SRVPID $XVFB 2>/dev/null || true

if grep -q 'biome-miss\|mob-miss' "$OUT/bot.log" "$OUT/play.json.crash.log" 2>/dev/null; then
  echo "WARN world commands are being refused — check ops.json"; fi

if [ -s "$OUT/authentic.mp4" ]; then
  DUR=$("${FFPROBE:-/pkg/ffmpeg/4.2.2/bin/ffprobe}" -v error -show_entries format=duration -of csv=p=0 "$OUT/authentic.mp4")
  N=$(/usr/bin/python3 -c "import json;print(len(json.load(open('$OUT/play.json'))['events']))" 2>/dev/null || echo 0)
  echo "AUTHENTIC_OK ${DUR}s ${N}_events"
else
  echo NO_VIDEO_RECORDED
fi
