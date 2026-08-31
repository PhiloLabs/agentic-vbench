#!/bin/bash
# Render one P1 session: bot + capture. Fails fast if the Minecraft server is not up —
# a dead server previously wasted a full render slot (the bot exits with ECONNREFUSED and
# the capture then sits waiting for a viewer that never appears).
set -x
V=${1:?version tag}
MAXS=${2:-1800}          # capture ceiling; a multi-lap session needs more than the 30 min default
LAPS=${3:-1}
D="${WORK:-/tmp/agenticvbench-mc}/p1-mc"
cd "${TOOLS:-$HOME/text-dna/agenticvbench-claude/generator}"

if ! (exec 3<>/dev/tcp/127.0.0.1/25577) 2>/dev/null; then
  echo "SERVER_DOWN: nothing listening on 25577 — start paper.jar first"; exit 3
fi

rm -f $D/GO$V $D/DONE$V $D/play_$V.json $D/play_$V.json.crash.log; rm -rf $D/${V}_capture
P1_LAPS=$LAPS node bot_play8.js $D/play_$V.json $D/GO$V $D/DONE$V > $D/bot_$V.out 2>&1 &
BOT=$!
sleep 20
if ! kill -0 $BOT 2>/dev/null; then echo "BOT_DIED_EARLY"; tail -5 $D/bot_$V.out; exit 4; fi
/usr/bin/python3 capture_mc.py $D/${V}_capture $D/GO$V $D/DONE$V $MAXS
kill $BOT 2>/dev/null
echo "SESSION_DONE $V"
