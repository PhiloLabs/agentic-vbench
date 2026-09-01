#!/bin/bash
# Prove, from inside the run's own network namespace, that the GT-leak paths are
# unreachable and that only the model transport is open. Every scored run calls
# this before and after the agent, and the output is the evidence behind the
# "verified per run" claim in scores.md. A failure here voids the run.
#
# Usage: ./net_guard.sh <label> <logfile>
set -euo pipefail

LABEL="${1:?usage: ./net_guard.sh <label> <logfile>}"
LOG="${2:?logfile required}"
GATE=${AVB_GATE:-avb-netgate}
IMAGE=${TASK_IMAGE:-agentic-vbench-openttgames}

MUST_BLOCK=(
  https://github.com
  https://raw.githubusercontent.com
  https://lab.osai.ai
  https://www.google.com
)
# The agent harness itself is the only thing allowed out. Reaching this endpoint
# is inference, not lookup; the distinction is what audit_and_grade.sh enforces
# on the trajectory.
MUST_REACH=( https://api.openai.com/v1/models )

mkdir -p "$(dirname "$LOG")"
{
  echo "=== net_guard $LABEL @ $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
  # Capture once and slice locally. Piping `docker exec` into head/tail closes the
  # pipe early, which under `set -o pipefail` surfaces as SIGPIPE (141) and kills
  # the run -- intermittently, because it is a race with docker's own write.
  rules=$(docker exec "$GATE" iptables -L OUTPUT -n)
  echo "netgate policy: $(printf '%s\n' "$rules" | sed -n 1p)"
  echo "netgate ACCEPT rules: $(printf '%s\n' "$rules" | grep -c ACCEPT || true)"
} >> "$LOG"

fail=0
for u in "${MUST_BLOCK[@]}"; do
  code=$(docker run --rm --network "container:$GATE" "$IMAGE" \
           curl -s -o /dev/null -w '%{http_code}' --max-time 8 "$u" 2>/dev/null || true)
  if [ "$code" = "000" ]; then
    echo "  BLOCKED ok   $u" | tee -a "$LOG"
  else
    echo "  REACHABLE !! $u -> $code" | tee -a "$LOG"; fail=1
  fi
done

for u in "${MUST_REACH[@]}"; do
  code=$(docker run --rm --network "container:$GATE" "$IMAGE" \
           curl -s -o /dev/null -w '%{http_code}' --max-time 8 "$u" 2>/dev/null || true)
  if [ "$code" = "000" ]; then
    echo "  UNREACHABLE !! $u (model transport down)" | tee -a "$LOG"; fail=1
  else
    echo "  REACHABLE ok $u -> $code" | tee -a "$LOG"
  fi
done

if [ "$fail" -ne 0 ]; then
  echo "net_guard FAILED for $LABEL - do not score this run" | tee -a "$LOG"
  exit 1
fi
echo "net_guard PASSED for $LABEL" | tee -a "$LOG"
