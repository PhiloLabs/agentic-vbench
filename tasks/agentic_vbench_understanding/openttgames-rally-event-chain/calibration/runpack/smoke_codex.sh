#!/bin/bash
# Minimal end-to-end proof that a scored Codex run is possible under the locked
# allowlist, before committing hours to the real one. It answers exactly three
# questions and then stops:
#
#   1. does the CLI install into the frozen image;
#   2. under `netgate lock`, are the ground-truth paths unreachable;
#   3. under `netgate lock`, does a real model request still complete.
#
# It deliberately does NOT touch the calibration workspace, so the official run
# starts from a pristine container. Logs land in ../rollouts/ as evidence.
#
# Usage: ./smoke_codex.sh [codex-version]
set -euo pipefail

VER="${1:-0.147.0}"
TASK="$(cd "$(dirname "$0")/../.." && pwd)"
IMAGE=${TASK_IMAGE:-agentic-vbench-openttgames}
GATE=avb-netgate
CNAME=avb-smoke-codex
R="$(cd "$(dirname "$0")/.." && pwd)/rollouts"
LOG="$R/smoke_codex.log"
NETLOG="$R/smoke_codex.netguard.log"
mkdir -p "$R"; : > "$LOG"

log() { echo "$@" | tee -a "$LOG"; }

log "=== smoke @ $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
log "image: $IMAGE   codex: $VER   task commit: $(git -C "$TASK" rev-parse --short HEAD)"

"$(dirname "$0")/netgate.sh" up | tee -a "$LOG"

docker rm -f "$CNAME" >/dev/null 2>&1 || true
docker run -d --name "$CNAME" --network "container:$GATE" -w /workspace "$IMAGE" \
  sh -c 'sleep infinity' >/dev/null
log "smoke container up: $CNAME (netns shared with $GATE)"

log "--- 1. install codex@$VER ---"
docker exec "$CNAME" sh -c "
  apt-get update -qq && apt-get install -y -qq --no-install-recommends nodejs npm >/dev/null 2>&1
  npm install -g @openai/codex@$VER >/dev/null 2>&1
  codex --version
" 2>&1 | tee -a "$LOG"

if [ -f "$HOME/.codex/auth.json" ]; then
  docker exec "$CNAME" mkdir -p /opt/codex-home
  docker cp "$HOME/.codex/auth.json" "$CNAME:/opt/codex-home/auth.json"
  docker exec "$CNAME" chmod 600 /opt/codex-home/auth.json
  log "staged CODEX_HOME credential from the host login"
fi

log "--- 2. lock the gate, then re-prove isolation ---"
"$(dirname "$0")/netgate.sh" lock | tee -a "$LOG"
"$(dirname "$0")/net_guard.sh" smoke-locked "$NETLOG" | tee -a "$LOG"

log "--- 2b. same check from inside the smoke container itself ---"
docker exec "$CNAME" sh -c '
for u in https://github.com https://raw.githubusercontent.com https://lab.osai.ai https://www.google.com https://api.openai.com/v1/models; do
  printf "  %-42s -> %s\n" "$u" "$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$u" || true)"
done' 2>&1 | tee -a "$LOG"

log "--- 3. real model request under lock ---"
set +e
docker exec -e CODEX_HOME=/opt/codex-home \
  ${OPENAI_API_KEY:+-e OPENAI_API_KEY="$OPENAI_API_KEY"} \
  "$CNAME" sh -c '
    cd /workspace
    codex exec --json --skip-git-repo-check --sandbox read-only --config tools.web_search=false \
      "Reply with exactly this token and nothing else: AVB_SMOKE_OK" < /dev/null
  ' > "$R/smoke_codex.jsonl" 2> "$R/smoke_codex.err"
rc=$?
set -e
log "codex exit: $rc   trajectory lines: $(wc -l < "$R/smoke_codex.jsonl")"

if grep -q "AVB_SMOKE_OK" "$R/smoke_codex.jsonl" 2>/dev/null; then
  log "SMOKE PASSED: model reachable and responding under the locked allowlist"
else
  log "SMOKE FAILED: no AVB_SMOKE_OK in the trajectory"
  log "--- stderr tail ---"; tail -20 "$R/smoke_codex.err" | tee -a "$LOG"
  exit 1
fi
