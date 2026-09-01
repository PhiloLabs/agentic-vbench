#!/bin/bash
# Periodically copy a running agent's workspace out of its container, so an
# interrupted run still leaves its partial work behind.
#
# Purely observational: it never writes into the container, never touches the
# agent, and never touches the frozen task. It exists because a run killed by
# cost, timeout or crash otherwise leaves its intermediate products stranded in
# a container that later gets re-staged. The trajectory itself is already safe --
# the runner redirects it to the host line by line.
#
# materials/ is skipped on purpose: it is the 11 GB baked video.
#
# Usage: ./snapshot.sh <container> <label> [interval-seconds]
set -uo pipefail

CNAME="${1:?usage: ./snapshot.sh <container> <label> [interval]}"
LABEL="${2:?label required}"
INT="${3:-180}"
R="$(cd "$(dirname "$0")/.." && pwd)/rollouts/snapshots/$LABEL"
mkdir -p "$R"

while docker inspect "$CNAME" --format '{{.State.Running}}' 2>/dev/null | grep -q true; do
  TS=$(date -u +%Y%m%dT%H%M%SZ)
  D="$R/$TS"; mkdir -p "$D"
  for sub in output work; do
    docker cp "$CNAME:/workspace/$sub" "$D/$sub" >/dev/null 2>&1
  done
  # anything the agent dropped at the workspace root, excluding the baked media
  docker exec "$CNAME" sh -c 'find /workspace -maxdepth 1 -type f' 2>/dev/null | while read -r f; do
    docker cp "$CNAME:$f" "$D/" >/dev/null 2>&1
  done
  n=$(find "$D" -type f 2>/dev/null | wc -l | tr -d ' ')
  # drop empty snapshots so the directory stays readable
  if [ "$n" -eq 0 ]; then rmdir -p "$D" 2>/dev/null; else echo "$TS  $n files" >> "$R/index.txt"; fi
  sleep "$INT"
done
echo "$(date -u +%Y%m%dT%H%M%SZ)  container stopped; snapshotting ended" >> "$R/index.txt"
