#!/bin/bash
# Decide whether a run is genuinely hung. Read-only; never kills anything.
#
# A single indicator is not enough, and getting this wrong is expensive in both
# directions. Two real cases from this task:
#   - transcript plateaued for minutes while ffmpeg burned 2000 CPU-seconds
#     decoding the whole video for the agent: healthy, nearly killed by mistake
#   - agy.log frozen, CPU 0.2%, no children: genuinely hung
# The parent can sit near-idle while a child does all the work, so child CPU
# accumulation is checked separately from container CPU.
#
# Hung only if ALL of these hold across the sample window:
#   1. native transcript line count unchanged
#   2. agy.log mtime unchanged
#   3. container CPU near zero
#   4. no child process accumulating CPU
#   5. no new tool output appearing in the workspace
#   6. the native log shows no pending background-task / retry / polling state
#
# Condition 6 and a long window matter because a completed child process does not
# mean the agent is finished: the background-task completion notification can
# arrive minutes later, and the agent sits in futex_wait until it does. Default
# window is therefore 600s, not 120s.
#
# Usage: ./liveness.sh <container> [window-seconds]
set -uo pipefail
C="${1:?usage: ./liveness.sh <container> [seconds]}"
W="${2:-600}"

snap() {
  docker exec "$C" sh -c '
    T=$(find /root/.gemini/antigravity-cli/brain -name transcript.jsonl 2>/dev/null | head -1)
    echo "$([ -n "$T" ] && wc -l < "$T" || echo 0)|$(stat -c %Y /workspace/agy.log 2>/dev/null || echo 0)|$(find /workspace/work -type f 2>/dev/null | wc -l)|$(awk "{s+=\$14+\$15} END{print s+0}" /proc/[0-9]*/stat 2>/dev/null)"' 2>/dev/null
}
cpu() { docker stats --no-stream --format '{{.CPUPerc}}' "$C" 2>/dev/null | tr -d '%'; }

A=$(snap); CA=$(cpu)
sleep "$W"
B=$(snap); CB=$(cpu)

IFS='|' read -r t1 m1 f1 j1 <<< "$A"
IFS='|' read -r t2 m2 f2 j2 <<< "$B"
dj=$(( ${j2:-0} - ${j1:-0} ))
peak=$(awk -v a="${CA:-0}" -v b="${CB:-0}" 'BEGIN{print (a>b)?a:b}')

echo "  window ${W}s"
printf "  1 transcript lines : %-8s -> %-8s %s\n" "$t1" "$t2" "$([ "$t1" = "$t2" ] && echo STATIC || echo MOVING)"
printf "  2 agy.log mtime    : %-8s -> %-8s %s\n" "$m1" "$m2" "$([ "$m1" = "$m2" ] && echo STATIC || echo MOVING)"
printf "  3 container CPU    : peak %-6s%% %s\n" "$peak" "$(awk -v p="$peak" 'BEGIN{print (p<5)?"NEAR-ZERO":"ACTIVE"}')"
printf "  4 child CPU jiffies: +%-8s %s\n" "$dj" "$([ "$dj" -gt 50 ] && echo ACCUMULATING || echo IDLE)"
printf "  5 work files       : %-8s -> %-8s %s\n" "$f1" "$f2" "$([ "$f1" = "$f2" ] && echo STATIC || echo GROWING)"

# 6: is the CLI explicitly parked waiting on something?
PEND=$(docker exec "$C" sh -c '
  T=$(find /root/.gemini/antigravity-cli/brain -name transcript.jsonl 2>/dev/null | head -1)
  { [ -n "$T" ] && tail -20 "$T"; tail -40 /workspace/agy.log 2>/dev/null; } \
    | grep -ciE "background task|waiting for|will notify|retry|polling|IDLE update" 2>/dev/null || echo 0' 2>/dev/null)
PEND=${PEND:-0}
printf "  6 pending-state hits: %-8s %s\n" "$PEND" "$([ "${PEND}" -gt 0 ] && echo "WAITING (not hung)" || echo NONE)"

hung=1
[ "${PEND}" -eq 0 ] || hung=0
[ "$t1" = "$t2" ] || hung=0
[ "$m1" = "$m2" ] || hung=0
awk -v p="$peak" 'BEGIN{exit (p<5)?0:1}' || hung=0
[ "$dj" -le 50 ] || hung=0
[ "$f1" = "$f2" ] || hung=0
echo
if [ "$hung" -eq 1 ]; then echo "  VERDICT: all five static -> genuinely hung"; exit 1
else echo "  VERDICT: progress detected -> NOT hung, leave it alone"; exit 0; fi
