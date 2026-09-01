#!/bin/bash
# Resume a Claude Code calibration run that was cut short by a rate-limit reset.
#
# This is a second session of ONE logical run, not a fresh run. It uses
# `claude --continue`, so the agent keeps the conversation it already had rather
# than rediscovering its own intermediate files as if a stranger had left them.
# Turns and wall time are additive across the sessions and must be reported that
# way; the reward comes from whatever output/solution.json finally exists.
#
# Deliberately NOT done here:
#   - no `netgate.sh up`: that subcommand does `docker rm -f` on the gate, and the
#     run container borrows the gate's network namespace via
#     `--network container:<gate>`. Destroying the gate breaks the run container's
#     networking permanently, taking the salvaged workdir with it. `install` and
#     `lock` change rules in place and are safe.
#   - no re-staging: stage_workspace.sh recreates the container, which would
#     delete the intermediate files this resume exists to build on.
#
# Usage: ./resume_claude.sh [model]
set -euo pipefail

CNAME=avb-run-claude
MODEL="${1:-claude-opus-4-8}"
TASK="$(cd "$(dirname "$0")/../.." && pwd)"
R="$(cd "$(dirname "$0")/.." && pwd)/rollouts"
SEG=2
mkdir -p "$R"

docker inspect "$CNAME" >/dev/null 2>&1 || { echo "FATAL: $CNAME is gone; the workdir cannot be resumed"; exit 1; }
docker exec "$CNAME" sh -c '[ -d /workspace/work ]' || { echo "FATAL: /workspace/work missing"; exit 1; }

SESS=$(docker exec "$CNAME" sh -c 'ls -t /root/.claude/projects/-workspace/*.jsonl 2>/dev/null | head -1' | tr -d '\r')
[ -n "$SESS" ] || { echo "FATAL: no resumable session found"; exit 1; }

"$(dirname "$0")/net_guard.sh" "claude-seg${SEG}-pre" "$R/claude.netguard.log"

{
  echo "harness:         Claude Code CLI"
  echo "harness version: $(docker exec "$CNAME" claude --version 2>/dev/null)"
  echo "model:           $MODEL"
  echo "segment:         $SEG of one logical run (resumed with --continue)"
  echo "session file:    $(basename "$SESS") ($(docker exec "$CNAME" wc -l < "$SESS" | tr -d ' ') lines carried over)"
  echo "workdir carried: $(docker exec "$CNAME" sh -c 'ls /workspace/work | wc -l' | tr -d ' ') files"
  echo "auth:            subscription OAuth (no API key staged)"
  echo "task commit:     $(git -C "$TASK" rev-parse HEAD)"
  echo "image:           ${TASK_IMAGE:-agentic-vbench-openttgames}"
  echo "rules sha256:    $(shasum -a 256 "$(dirname "$0")/AGENTS.md" | awk '{print $1}')"
  echo "started:         $(date -u +%Y-%m-%dT%H:%M:%SZ)"
} | tee "$R/claude_run_metadata.seg${SEG}.txt"

# The continuation prompt is deliberately neutral: it restates no part of the
# task and offers no approach. Same wording the Antigravity retry path uses.
docker exec "$CNAME" sh -c "
    if [ -f /opt/anthropic-key ]; then export ANTHROPIC_API_KEY=\$(cat /opt/anthropic-key); fi
    cd /workspace
    claude --continue -p 'Continue the task from where you stopped. Write the final answer to /workspace/output/solution.json.' \
      --model $MODEL \
      --allowedTools Bash Read Write Edit Glob Grep \
      --verbose --output-format stream-json \
      --disallowedTools WebFetch,WebSearch
  " > "$R/claude_${MODEL}.seg${SEG}.jsonl" 2> "$R/claude_${MODEL}.seg${SEG}.err" || true

"$(dirname "$0")/net_guard.sh" "claude-seg${SEG}-post" "$R/claude.netguard.log"
docker cp "$CNAME:/workspace/output/solution.json" "$R/claude_solution.json" 2>/dev/null \
  && echo "  solution.json harvested" \
  || echo "  no solution.json produced - incomplete run; do not report it as a scored calibration"

echo "segment $SEG rollout: $R/claude_${MODEL}.seg${SEG}.jsonl"
