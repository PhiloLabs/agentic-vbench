#!/bin/bash
# Official Antigravity calibration run.
#
# Three defects from the first attempt are addressed here.
#
# 1. stdout stream-json under-records. Measured on the 503 run: stdout captured
#    steps 0-76 and went silent the moment a long run_command started, while the
#    CLI kept working to step 186. The authoritative record is the CLI's own
#    native transcript under ~/.gemini/antigravity-cli/brain/<conv>/. That is the
#    artifact merged tasks ship, and it is harvested here unconditionally --
#    including after a failure, so a truncated run still yields a real record.
#
# 2. A dead executor used to hang. The 503 killed the agent at 06:26:51 but the
#    process sat idle until --print-timeout would have expired 2.5h later. A
#    watchdog now tails the CLI log and terminates promptly on a terminal error.
#
# 3. Transient 503s were fatal. Google returns "high demand ... try again later";
#    the CLI supports --continue, so the run now resumes the same conversation
#    with backoff instead of restarting from zero.
#
# Lookup is prohibited by the harness rules file and enforced after the fact by the
# transcript watchdog and audit scan -- this CLI exposes no flag to remove its web
# tools, and its server-side Search grounding executes provider-side, so the netgate
# cannot block it. A detected search voids the run. Ordinary egress is blocked at the
# container
# level (shared netgate namespace). Gemini's Search grounding is server-side and
# no network policy can see it, so audit_and_grade.sh scans the transcript.
#
# Usage: ./run_antigravity.sh [model] [max-attempts]
set -uo pipefail

CNAME=avb-run-antigravity
MODEL="${1:-gemini-3.5-flash-high}"
MAX_ATTEMPTS="${2:-4}"
TASK="$(cd "$(dirname "$0")/../.." && pwd)"
R="$(cd "$(dirname "$0")/.." && pwd)/rollouts"
mkdir -p "$R"

docker inspect "$CNAME" >/dev/null 2>&1 || { echo "run ./stage_workspace.sh antigravity first"; exit 1; }
"$(dirname "$0")/net_guard.sh" antigravity-pre "$R/antigravity.netguard.log"

for a in 1 2; do
  "$(dirname "$0")/netgate.sh" install >/dev/null
  if docker exec "$CNAME" sh -c '
       curl -fsSL https://antigravity.google/cli/install.sh | bash >/dev/null 2>&1
       export PATH="$HOME/.local/bin:$PATH"; agy --version' 2>&1 | sed 's/^/  /'; then break; fi
  [ "$a" = 2 ] && { echo "FATAL: agy install failed twice"; exit 1; }
done

"$(dirname "$0")/netgate.sh" lock

{
  echo "harness:         Antigravity CLI"
  echo "harness version: $(docker exec "$CNAME" sh -c 'export PATH="$HOME/.local/bin:$PATH"; agy --version' 2>/dev/null)"
  echo "model:           $MODEL"
  echo "task commit:     $(git -C "$TASK" rev-parse HEAD)"
  echo "image:           ${TASK_IMAGE:-agentic-vbench-openttgames}"
  echo "rules sha256:   $(shasum -a 256 "$(dirname "$0")/AGENTS.md" | awk '{print $1}')"
  echo "started:         $(date -u +%Y-%m-%dT%H:%M:%SZ)"
} | tee "$R/antigravity_run_metadata.txt"

# Copy the CLI's own transcript out. Safe to call at any point, including after a
# crash; this is the record scores.md cites.
harvest() {
  local tag="$1"
  docker exec "$CNAME" sh -c '
    T=$(find /root/.gemini/antigravity-cli/brain -name transcript.jsonl 2>/dev/null | head -1)
    F=$(find /root/.gemini/antigravity-cli/brain -name transcript_full.jsonl 2>/dev/null | head -1)
    [ -n "$T" ] && cp "$T" /workspace/native_transcript.jsonl
    [ -n "$F" ] && cp "$F" /workspace/native_transcript_full.jsonl' 2>/dev/null
  docker cp "$CNAME:/workspace/native_transcript.jsonl"      "$R/antigravity_${MODEL}.native.jsonl"      >/dev/null 2>&1
  docker cp "$CNAME:/workspace/native_transcript_full.jsonl" "$R/antigravity_${MODEL}.native_full.jsonl" >/dev/null 2>&1
  docker cp "$CNAME:/workspace/agy.log"                      "$R/antigravity_${MODEL}.agy.log"           >/dev/null 2>&1
  echo "  harvested native transcript ($tag): $(wc -l < "$R/antigravity_${MODEL}.native.jsonl" 2>/dev/null || echo 0) lines"
}

for attempt in $(seq 1 "$MAX_ATTEMPTS"); do
  echo "=== attempt $attempt/$MAX_ATTEMPTS ==="

  # Watchdog runs from a copied-in file; see runpack/watchdog.sh for why.
  docker cp "$(dirname "$0")/watchdog.sh" "$CNAME:/tmp/watchdog.sh" >/dev/null 2>&1
  docker exec "$CNAME" chmod +x /tmp/watchdog.sh
  docker exec -d "$CNAME" /tmp/watchdog.sh

  if [ "$attempt" -eq 1 ]; then
    docker exec "$CNAME" sh -c "
      if [ -f /opt/gemini-key ]; then export GEMINI_API_KEY=\$(cat /opt/gemini-key); fi
      export PATH=\"\$HOME/.local/bin:\$PATH\"
      cd /workspace
      agy -p \"\$(cat instruction.md)\" --model $MODEL \
        --output-format stream-json --dangerously-skip-permissions \
        --print-timeout 3h --log-file /workspace/agy.log
    " >> "$R/antigravity_${MODEL}.jsonl" 2>> "$R/antigravity_${MODEL}.err"
  else
    docker exec "$CNAME" sh -c "
      if [ -f /opt/gemini-key ]; then export GEMINI_API_KEY=\$(cat /opt/gemini-key); fi
      export PATH=\"\$HOME/.local/bin:\$PATH\"
      cd /workspace
      agy --continue -p \"Continue the task from where you stopped. Write the final answer to /workspace/output/solution.json.\" \
        --model $MODEL --output-format stream-json --dangerously-skip-permissions \
        --print-timeout 3h --log-file /workspace/agy.log
    " >> "$R/antigravity_${MODEL}.jsonl" 2>> "$R/antigravity_${MODEL}.err"
  fi

  docker exec "$CNAME" sh -c 'pkill -f "grep -qE agent executor" ; true' 2>/dev/null
  harvest "attempt $attempt"

  if docker exec "$CNAME" test -f /tmp/agy_contaminated 2>/dev/null; then
    echo "  CONTAMINATED: the agent invoked server-side web search."
    echo "  This run is void. Do not score it. Evidence is in the harvested transcript."
    harvest "contaminated"
    "$(dirname "$0")/net_guard.sh" antigravity-post "$R/antigravity.netguard.log" || true
    exit 2
  fi
  if docker exec "$CNAME" test -f /workspace/output/solution.json 2>/dev/null; then
    echo "  solution.json produced - stopping"; break
  fi
  # The CLI reports terminal failure with several different wordings; keying the
  # retry only on the watchdog flag missed "Agent execution terminated due to
  # error." and silently skipped all four retries on a run that had in fact failed.
  # OOM is neither a provider fault nor agent difficulty: the container hit its
  # memory ceiling and the kernel killed the CLI. Retrying changes nothing, so
  # classify it separately, stop, and surface it for a resource fix.
  OOMK=$(docker inspect "$CNAME" --format '{{.State.OOMKilled}}' 2>/dev/null)
  OOMEV=$(docker exec "$CNAME" sh -c 'sed -n "s/^oom_kill \([0-9]*\)/\1/p" /sys/fs/cgroup/memory.events 2>/dev/null' 2>/dev/null)
  if [ "$OOMK" = "true" ] || [ "${OOMEV:-0}" != "0" ]; then
    echo "  OOM-KILLED: container hit its memory limit (OOMKilled=$OOMK cgroup oom_kill=${OOMEV:-0})."
    echo "  This is a resource-budget failure, not a provider error and not agent"
    echo "  difficulty. Not retrying; raise the Docker VM headroom and rerun."
    harvest "oom"
    "$(dirname "$0")/net_guard.sh" antigravity-post "$R/antigravity.netguard.log" || true
    exit 3
  fi

  ERRSTATUS=$(grep -o '"status": *"ERROR"' "$R/antigravity_${MODEL}.jsonl" 2>/dev/null | head -1)
  if ! docker exec "$CNAME" test -f /tmp/agy_dead 2>/dev/null && [ -z "$ERRSTATUS" ]; then
    echo "  run ended without a terminal error and without solution.json - not retrying"; break
  fi
  [ -n "$ERRSTATUS" ] && echo "  result status=ERROR detected in stream; treating as retryable"

  # Keep every failed attempt separately: the accepted result must come from one
  # complete clean attempt, not a blend of partial ones.
  AB="$R/aborted"; mkdir -p "$AB"
  for x in jsonl err native.jsonl native_full.jsonl agy.log; do
    [ -f "$R/antigravity_${MODEL}.${x}" ] && cp "$R/antigravity_${MODEL}.${x}" "$AB/attempt${attempt}.antigravity_${MODEL}.${x}"
  done

  # Classify from this attempt's own archived artifacts, never from the shared
  # agy.log: the CLI truncates that on each --log-file open, so provider evidence
  # survives on some attempts and vanishes on others. See error_signature.sh.
  SIG=$("$(dirname "$0")/error_signature.sh" \
        "$AB/attempt${attempt}.antigravity_${MODEL}.jsonl" \
        "$AB/attempt${attempt}.antigravity_${MODEL}.agy.log" 2>/dev/null)
  CLASS="${SIG%%|*}"
  echo "  failure signature: ${SIG:-unknown}"
  if [ -n "$CLASS" ] && [ "$CLASS" = "${PREV_CLASS:-}" ]; then
    echo "  same failure class twice in a row (${CLASS}) - stopping rather than"
    echo "  consuming the remaining retry budget on a standing condition"
    break
  fi
  PREV_CLASS="$CLASS"

  echo "  terminal executor error detected (503 class); backing off before resuming"
  [ "$attempt" -lt "$MAX_ATTEMPTS" ] && sleep $((60 * attempt))
done

"$(dirname "$0")/net_guard.sh" antigravity-post "$R/antigravity.netguard.log"
docker cp "$CNAME:/workspace/output/solution.json" "$R/antigravity_solution.json" 2>/dev/null \
  || echo "  no solution.json produced - incomplete run; do not report it as a scored calibration"

echo "native transcript: $R/antigravity_${MODEL}.native.jsonl"
echo "next: ./audit_and_grade.sh antigravity $R/antigravity_${MODEL}.native.jsonl"
