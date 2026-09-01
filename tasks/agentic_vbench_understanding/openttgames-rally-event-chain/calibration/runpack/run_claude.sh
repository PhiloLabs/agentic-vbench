#!/bin/bash
# Official Claude Code calibration run.
# Lookup is blocked at the harness level by removing the web tools, and at the
# container level by the shared netgate namespace. Tool execution is granted with
# --allowedTools rather than --permission-mode bypassPermissions: the latter is
# refused outright when the CLI runs as root, which is how the frozen image runs.
# This is the counterpart of Codex's --sandbox workspace-write.
# Usage: ./run_claude.sh [model]        e.g. opus-4.8 | fable-5
set -euo pipefail

CNAME=avb-run-claude
MODEL="${1:-claude-opus-4-8}"
TASK="$(cd "$(dirname "$0")/../.." && pwd)"
R="$(cd "$(dirname "$0")/.." && pwd)/rollouts"
mkdir -p "$R"

docker inspect "$CNAME" >/dev/null 2>&1 || { echo "run ./stage_workspace.sh claude first"; exit 1; }
"$(dirname "$0")/net_guard.sh" claude-pre "$R/claude.netguard.log"

# Refresh the install allowlist immediately before use, and retry once: a CDN
# mirror can rotate to an address that was not resolvable a minute earlier.
for attempt in 1 2; do
  "$(dirname "$0")/netgate.sh" install >/dev/null
  if docker exec "$CNAME" sh -c '
       apt-get update -qq && apt-get install -y -qq --no-install-recommends nodejs npm >/dev/null 2>&1
       npm install -g @anthropic-ai/claude-code >/dev/null 2>&1
       claude --version
     ' 2>&1 | sed 's/^/  /'; then
    break
  fi
  [ "$attempt" = 2 ] && { echo "FATAL: Claude Code CLI install failed twice"; exit 1; }
  echo "  install attempt $attempt failed; refreshing allowlist and retrying"
done

# Tighten the gate before scoring: the package hosts needed for the install
# above must not stay reachable during the run itself.
"$(dirname "$0")/netgate.sh" lock

{
  echo "harness:         Claude Code CLI"
  echo "harness version: $(docker exec "$CNAME" claude --version 2>/dev/null)"
  echo "model:           $MODEL"
  echo "task commit:     $(git -C "$TASK" rev-parse HEAD)"
  echo "image:           ${TASK_IMAGE:-agentic-vbench-openttgames}"
  echo "rules sha256:   $(shasum -a 256 "$(dirname "$0")/AGENTS.md" | awk '{print $1}')"
  echo "started:         $(date -u +%Y-%m-%dT%H:%M:%SZ)"
} | tee "$R/claude_run_metadata.txt"


# Only export a key when one was actually staged. Exporting an empty
# ANTHROPIC_API_KEY, or any key at all, overrides the subscription OAuth login
# and puts the run back on metered billing.
docker exec "$CNAME" sh -c "
    if [ -f /opt/anthropic-key ]; then export ANTHROPIC_API_KEY=\$(cat /opt/anthropic-key); fi
    cd /workspace
    claude -p \"\$(cat instruction.md)\" \
      --model $MODEL \
      --allowedTools Bash Read Write Edit Glob Grep \
      --verbose --output-format stream-json \
      --disallowedTools WebFetch,WebSearch
  " > "$R/claude_$MODEL.jsonl" 2> "$R/claude_$MODEL.err" || true

"$(dirname "$0")/net_guard.sh" claude-post "$R/claude.netguard.log"
docker cp "$CNAME:/workspace/output/solution.json" "$R/claude_solution.json" 2>/dev/null \
  || echo "  no solution.json produced - incomplete run; do not report it as a scored calibration"

echo "rollout: $R/claude_$MODEL.jsonl"
echo "next:    ./audit_and_grade.sh claude $R/claude_$MODEL.jsonl"
