#!/bin/bash
# Minimal end-to-end proof that a scored Claude Code run is possible under the
# locked allowlist, and resolution of the exact model id to pin. Mirrors
# smoke_codex.sh; deliberately does not touch the calibration workspace.
# Usage: ./smoke_claude.sh [candidate-model-id ...]
set -euo pipefail

TASK="$(cd "$(dirname "$0")/../.." && pwd)"
IMAGE=${TASK_IMAGE:-agentic-vbench-openttgames}
GATE=avb-netgate
CNAME=avb-smoke-claude
R="$(cd "$(dirname "$0")/.." && pwd)/rollouts"
LOG="$R/smoke_claude.log"
NETLOG="$R/smoke_claude.netguard.log"
mkdir -p "$R"; : > "$LOG"
CANDIDATES=("$@"); [ ${#CANDIDATES[@]} -eq 0 ] && CANDIDATES=(claude-opus-4-8 opus-4.8 claude-fable-5)

log() { echo "$@" | tee -a "$LOG"; }
log "=== claude smoke @ $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
log "image: $IMAGE   task commit: $(git -C "$TASK" rev-parse --short HEAD)"

"$(dirname "$0")/netgate.sh" up | tee -a "$LOG"
docker rm -f "$CNAME" >/dev/null 2>&1 || true
docker run -d --name "$CNAME" --network "container:$GATE" -w /workspace "$IMAGE" \
  sh -c 'sleep infinity' >/dev/null
log "smoke container up: $CNAME"

log "--- 1. install Claude Code CLI ---"
docker exec "$CNAME" sh -c '
  apt-get update -qq && apt-get install -y -qq --no-install-recommends nodejs npm >/dev/null 2>&1
  npm install -g @anthropic-ai/claude-code >/dev/null 2>&1
  claude --version
' 2>&1 | tee -a "$LOG"

docker cp "$HOME/.avb_anthropic_key" "$CNAME:/opt/anthropic-key" >/dev/null
docker exec "$CNAME" chmod 600 /opt/anthropic-key
log "staged Anthropic credential file"

log "--- 2. lock the gate, re-prove isolation ---"
"$(dirname "$0")/netgate.sh" lock | tee -a "$LOG"
"$(dirname "$0")/net_guard.sh" claude-smoke-locked "$NETLOG" | tee -a "$LOG"

log "--- 2b. from inside the smoke container ---"
docker exec "$CNAME" sh -c '
for u in https://github.com https://raw.githubusercontent.com https://lab.osai.ai https://www.google.com https://api.anthropic.com/v1/models; do
  printf "  %-45s -> %s\n" "$u" "$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$u" || true)"
done' 2>&1 | tee -a "$LOG"

log "--- 3. resolve the model id (no defaults) ---"
RESOLVED=""
for m in "${CANDIDATES[@]}"; do
  set +e
  out=$(docker exec "$CNAME" sh -c "
    export ANTHROPIC_API_KEY=\$(cat /opt/anthropic-key)
    cd /workspace
    claude -p 'Reply with exactly: AVB_SMOKE_OK' --model $m \
      --output-format stream-json --verbose \
      --disallowedTools WebFetch,WebSearch < /dev/null" 2>&1)
  rc=$?
  set -e
  if echo "$out" | grep -q "AVB_SMOKE_OK"; then
    log "  $m -> OK"; RESOLVED="$m"
    echo "$out" > "$R/smoke_claude.jsonl"
    break
  else
    log "  $m -> rejected (exit $rc): $(echo "$out" | tr '\n' ' ' | cut -c1-160)"
  fi
done

if [ -z "$RESOLVED" ]; then
  log "SMOKE FAILED: no candidate model id resolved"; exit 1
fi
log "RESOLVED MODEL ID: $RESOLVED"
echo "$RESOLVED" > "$R/claude_resolved_model.txt"
log "SMOKE PASSED: Claude Code reachable and responding under the locked allowlist"
