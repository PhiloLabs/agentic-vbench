#!/bin/bash
# Containerised calibration arm.
#
#   run_arm.sh <arm-name> <model> <effort> [prompt-file]
#
# The agent CLI runs on the host because it needs network to reach its own
# API. Every action it takes on the task goes through the MCP proxy into a
# frozen `--network none` container built from environment/Dockerfile. The
# truth tree is mode 000 for the whole run, so a read-only-sandboxed agent
# cannot chmod it back and cannot see it.
set -uo pipefail

ARM=${1:?arm name}; MODEL=${2:?model}; EFFORT=${3:?effort}
HERE=$(cd "$(dirname "$0")" && pwd)          # this generator/ directory
ROOT=${AVB_CALIB_ROOT:-$PWD/avb_calib}        # where run directories are written
PROMPT=${4:-$HERE/PROMPT_container.md}
IMAGE=${AVB_IMAGE:-avb-standing-census:v6}
CT=${AVB_CT:-avb_task}
# Directories holding the ground truth and the generator's own outputs. They are
# made mode 000 for the whole run. Required, deliberately without a default, so
# that a calibration cannot silently run unlocked.
: "${AVB_LOCK_DIRS:?set AVB_LOCK_DIRS to the space-separated directories holding the truth}"
read -r -a LOCK <<< "$AVB_LOCK_DIRS"
RUN=$ROOT/run/$ARM
STAGING=$RUN/staging
CWD=$RUN/cwd

rm -rf "$RUN"; mkdir -p "$STAGING" "$CWD"
cp "$PROMPT" "$RUN/prompt.md"

unlock() { for d in "${LOCK[@]}"; do [ -e "$d" ] && chmod 755 "$d"; done; }
trap unlock EXIT INT TERM

# fresh container, empty output
docker rm -f "$CT" >/dev/null 2>&1
docker run -d --name "$CT" --network none --cpus 4 --memory 8g \
  "$IMAGE" sleep infinity >/dev/null || exit 1
docker exec "$CT" bash -lc 'rm -rf /workspace/work/* /workspace/output/*; mkdir -p /workspace/work /workspace/output'
docker exec "$CT" sha256sum /workspace/materials/session.mp4 > "$RUN/media_sha256.txt"
docker exec "$CT" bash -lc 'python3 -c "import socket;socket.gethostbyname(\"huggingface.co\")"' \
  > "$RUN/network_check.txt" 2>&1

for d in "${LOCK[@]}"; do [ -e "$d" ] && chmod 000 "$d"; done

date +%s > "$RUN/t0"
AVB_STAGING="$STAGING" AVB_CT="$CT" \
codex exec --strict-config --model "$MODEL" -c model_reasoning_effort="$EFFORT" \
  -c tools.web_search=false \
  -c mcp_servers.task.command=python3 \
  -c mcp_servers.task.args="[\"$HERE/container_mcp.py\"]" \
  -c mcp_servers.task.env="{AVB_STAGING=\"$STAGING\",AVB_CT=\"$CT\"}" \
  -c mcp_servers.task.startup_timeout_sec=60 \
  -c mcp_servers.task.default_tools_approval_mode=\"auto\" \
  -c mcp_servers.task.tools.exec.approval_mode=\"auto\" \
  -c mcp_servers.task.tools.fetch.approval_mode=\"auto\" \
  -c mcp_servers.task.tools.exec.output_token_limit=40000 \
  -c mcp_servers.task.tool_timeout_sec=1800 \
  --sandbox read-only -C "$CWD" --skip-git-repo-check --json \
  < "$RUN/prompt.md" > "$RUN/transcript.jsonl" 2> "$RUN/stderr.log" &
P=$!
( sleep 21600; kill -9 $P 2>/dev/null ) & G=$!
wait $P 2>/dev/null; kill $G 2>/dev/null
date +%s > "$RUN/t1"
unlock

docker cp "$CT:/workspace/output/solution.json" "$RUN/solution.json" 2>/dev/null \
  || echo "NO SOLUTION WRITTEN" | tee "$RUN/solution_missing.txt"
docker exec "$CT" bash -lc 'ls -la /workspace/output /workspace/work | head -40' > "$RUN/container_ls.txt" 2>&1

echo "$ARM done in $(( $(cat "$RUN/t1") - $(cat "$RUN/t0") ))s"
echo "mcp calls: $(wc -l < "$RUN/mcp_calls.log" 2>/dev/null || echo 0)"
