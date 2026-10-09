#!/bin/bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
MANUAL_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)
REPO_ROOT=$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)
VIDEO=${ROBOCUP_VIDEO:?Set ROBOCUP_VIDEO to the pinned match.mp4}
: "${ANTHROPIC_API_KEY:?Set ANTHROPIC_API_KEY}"
: "${CLAUDE_CODE_VERSION:?Set CLAUDE_CODE_VERSION to an audited exact version}"

MODEL=${CLAUDE_MODEL:-anthropic/claude-opus-4-8}
BASE_URL=${ANTHROPIC_BASE_URL:-https://api.anthropic.com}
API_HOST=${ANTHROPIC_API_HOST:-api.anthropic.com}
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
JOB_NAME=${JOB_NAME:-robocup-claude-final-$STAMP}
PREPARED_TASK=${PREPARED_TASK:-/tmp/$JOB_NAME-task}
TIMEOUT_MULTIPLIER=${AGENT_TIMEOUT_MULTIPLIER:-1}

python3 "$MANUAL_DIR/prepare_task.py" \
  --agent claude \
  --video "$VIDEO" \
  --output "$PREPARED_TASK" \
  --cli-version "$CLAUDE_CODE_VERSION"

cd "$REPO_ROOT"
harbor run \
  --path "$PREPARED_TASK" \
  --env docker \
  --agent claude-code \
  --model "$MODEL" \
  --agent-kwarg "reasoning_effort=xhigh" \
  --agent-kwarg "version=$CLAUDE_CODE_VERSION" \
  --allow-agent-host "$API_HOST" \
  --agent-env 'ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}' \
  --agent-env 'ANTHROPIC_BASE_URL=${ANTHROPIC_BASE_URL:-https://api.anthropic.com}' \
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
