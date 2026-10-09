#!/bin/bash
# Containerised calibration arm, Claude Code.
#
#   run_claude.sh <arm-name> <model>
#
# Same shape as run_arm.sh: the CLI runs on the host because it needs network,
# and every action on the task goes through the MCP proxy into the frozen
# `--network none` container. Here the lockdown is stronger than codex's: the
# only tools the model is given are the two proxy tools plus Read, so it has
# no host shell at all.
set -uo pipefail

ARM=${1:?arm name}; MODEL=${2:?model}
HERE=$(cd "$(dirname "$0")" && pwd)          # this generator/ directory
ROOT=${AVB_CALIB_ROOT:-$PWD/avb_calib}        # where run directories are written
PROMPT=${3:-$HERE/PROMPT_container.md}
IMAGE=${AVB_IMAGE:-avb-standing-census:v6}
CT=${AVB_CT:-avb_task}
# Directories holding the ground truth and the generator's own outputs. They are
# made mode 000 for the whole run. Required, deliberately without a default, so
# that a calibration cannot silently run unlocked.
: "${AVB_LOCK_DIRS:?set AVB_LOCK_DIRS to the space-separated directories holding the truth}"
read -r -a LOCK <<< "$AVB_LOCK_DIRS"
RUN=$ROOT/run/$ARM; STAGING=$RUN/staging; CWD=$RUN/cwd

rm -rf "$RUN"; mkdir -p "$STAGING" "$CWD"
cp "$PROMPT" "$RUN/prompt.md"
python3 - "$HERE/container_mcp.py" "$STAGING" "$CT" > "$RUN/mcp.json" <<'PYJ'
import json, sys
proxy, staging, ct = sys.argv[1:4]
print(json.dumps({"mcpServers": {"task": {
    "command": "python3", "args": [proxy],
    "env": {"AVB_STAGING": staging, "AVB_CT": ct}}}}, indent=2))
PYJ

unlock() { for d in "${LOCK[@]}"; do [ -e "$d" ] && chmod 755 "$d"; done; }
trap unlock EXIT INT TERM

docker rm -f "$CT" >/dev/null 2>&1
docker run -d --name "$CT" --network none --cpus 4 --memory 8g \
  "$IMAGE" sleep infinity >/dev/null || exit 1
docker exec "$CT" bash -lc 'rm -rf /workspace/work/* /workspace/output/*; mkdir -p /workspace/work /workspace/output'
docker exec "$CT" sha256sum /workspace/materials/session.mp4 > "$RUN/media_sha256.txt"
docker exec "$CT" bash -lc 'python3 -c "import socket;socket.gethostbyname(\"huggingface.co\")"' \
  > "$RUN/network_check.txt" 2>&1

for d in "${LOCK[@]}"; do [ -e "$d" ] && chmod 000 "$d"; done

date +%s > "$RUN/t0"
cd "$CWD" || exit 1
claude -p --model "$MODEL" \
  --mcp-config "$RUN/mcp.json" --strict-mcp-config \
  --allowedTools mcp__task__exec mcp__task__fetch Read \
  --disallowedTools Bash Write Edit NotebookEdit WebFetch WebSearch Task Glob Grep \
    Artifact ArtifactComments ArtifactData CronCreate CronDelete CronList DesignSync \
    EnterWorktree ExitWorktree ListAgents Monitor PushNotification RemoteTrigger \
    ReportFindings ScheduleWakeup SendMessage ShareOnboardingGuide Skill TaskStop \
    ToolSearch Workflow BashOutput KillShell TodoWrite \
  --permission-mode bypassPermissions \
  --output-format stream-json --verbose \
  < "$RUN/prompt.md" > "$RUN/transcript.jsonl" 2> "$RUN/stderr.log" &
P=$!
( sleep 14400; kill -9 $P 2>/dev/null ) & G=$!
wait $P 2>/dev/null; kill $G 2>/dev/null
date +%s > "$RUN/t1"
unlock

docker cp "$CT:/workspace/output/solution.json" "$RUN/solution.json" 2>/dev/null \
  || echo "NO SOLUTION WRITTEN" | tee "$RUN/solution_missing.txt"
echo "$ARM done in $(( $(cat "$RUN/t1") - $(cat "$RUN/t0") ))s"
echo "mcp calls: $(wc -l < "$RUN/mcp_calls.log" 2>/dev/null || echo 0)"
