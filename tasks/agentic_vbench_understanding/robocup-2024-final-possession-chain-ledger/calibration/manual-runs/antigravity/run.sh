#!/bin/bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
MANUAL_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)
REPO_ROOT=$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)
VIDEO=${ROBOCUP_VIDEO:?Set ROBOCUP_VIDEO to the pinned match.mp4}
: "${AGY_AUTH_JSON_PATH:?Set AGY_AUTH_JSON_PATH to the Harbor agy OAuth token file}"
test -s "$AGY_AUTH_JSON_PATH"

MODEL=${ANTIGRAVITY_MODEL:-google/gemini-3.1-pro}
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
JOB_NAME=${JOB_NAME:-robocup-antigravity-final-$STAMP}
PREPARED_TASK=${PREPARED_TASK:-/tmp/$JOB_NAME-task}
TIMEOUT_MULTIPLIER=${AGENT_TIMEOUT_MULTIPLIER:-1}

python3 "$MANUAL_DIR/prepare_task.py" \
  --agent antigravity \
  --video "$VIDEO" \
  --output "$PREPARED_TASK"

cd "$REPO_ROOT"
export AGY_AUTH_JSON_PATH
harbor run \
  --path "$PREPARED_TASK" \
  --env docker \
  --agent antigravity-cli \
  --model "$MODEL" \
  --agent-kwarg "reasoning_effort=high" \
  --allow-environment-host antigravity.google \
  --allow-environment-host antigravity-cli-auto-updater-974169037036.us-central1.run.app \
  --allow-environment-host storage.googleapis.com \
  --allow-agent-host antigravity.google \
  --allow-agent-host oauth2.googleapis.com \
  --allow-agent-host generativelanguage.googleapis.com \
  --allow-agent-host storage.googleapis.com \
  --allow-agent-host daily-cloudcode-pa.googleapis.com \
  --allow-agent-host www.googleapis.com \
  --allow-agent-host "*.googleapis.com" \
  --allow-agent-host lh3.googleusercontent.com \
  --allow-agent-host "*.googleusercontent.com" \
  --agent-timeout-multiplier "$TIMEOUT_MULTIPLIER" \
  --n-attempts 1 \
  --n-concurrent 1 \
  --max-retries 0 \
  --no-delete \
  --artifact /workspace/output/solution.json \
  --agent-include-logs '**/*' \
  --jobs-dir jobs \
  --job-name "$JOB_NAME" \
  --yes

python3 "$MANUAL_DIR/collect_run.py" --job-dir "$REPO_ROOT/jobs/$JOB_NAME"
