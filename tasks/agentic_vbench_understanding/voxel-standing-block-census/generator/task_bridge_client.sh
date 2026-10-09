#!/bin/bash
# Run one command inside the task environment. Usage:  ./task.sh '<command>'
# The working directory inside it is /workspace.
set -u
D="$(cd "$(dirname "$0")" && pwd)/_bridge"
ID="$(date +%s)_$$_$RANDOM"
printf '%s' "$1" > "$D/in/$ID.cmd.part"
mv "$D/in/$ID.cmd.part" "$D/in/$ID.cmd"
for _ in $(seq 1 3600); do
  if [ -f "$D/out/$ID.out" ]; then cat "$D/out/$ID.out"; rm -f "$D/out/$ID.out"; exit 0; fi
  sleep 0.5
done
echo "no response from the task environment after 30 minutes"; exit 1
