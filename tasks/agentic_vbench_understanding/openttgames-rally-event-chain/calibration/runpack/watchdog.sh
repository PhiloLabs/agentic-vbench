#!/bin/sh
# Runs inside the run container. Kept as a file rather than an inline sh -c
# string: the detection patterns contain both quote characters, and nesting them
# in a docker exec argument silently broke this watchdog once already.
#
# Two conditions end the run:
#   dead         - the CLI logged a terminal executor error and will now idle forever
#   contaminated - the agent reached Google's server-side search/grounding, which no
#                  container network policy can block, so the run must be voided
#
# Matching is on record TYPE and grounding infrastructure, never bare tool names:
# the staged rules file mentions those names in order to forbid them.
# The frozen image ships no procps, so pkill/pgrep do not exist here. Find the
# CLI by scanning /proc instead; this is why an earlier watchdog detected a
# condition but was unable to act on it.
kill_agy() {
  self=$$
  for d in /proc/[0-9]*; do
    pid=${d#/proc/}
    # Never match this watchdog: its own cmdline contains the pattern it hunts.
    [ "$pid" = "$self" ] && continue
    [ -r "$d/cmdline" ] || continue
    c=$(tr '\0' ' ' < "$d/cmdline" 2>/dev/null)
    case "$c" in
      *watchdog.sh*) continue ;;
    esac
    case "$c" in
      */agy\ *|agy\ *) kill -9 "$pid" 2>/dev/null ;;
    esac
  done
}

rm -f /tmp/agy_dead /tmp/agy_contaminated
while :; do
  if grep -qE "agent executor error|error in generator|Agent execution terminated" /workspace/agy.log 2>/dev/null; then
    touch /tmp/agy_dead
    sleep 5
    kill_agy
    exit 0
  fi
  T=$(find /root/.gemini/antigravity-cli/brain -name transcript.jsonl 2>/dev/null | head -1)
  if [ -n "$T" ]; then
    if grep -q '"type":"SEARCH_WEB"' "$T" 2>/dev/null \
       || grep -q 'grounding-api-redirect' "$T" 2>/dev/null \
       || grep -q 'vertexaisearch.cloud.google.com' "$T" 2>/dev/null; then
      touch /tmp/agy_contaminated
      kill_agy
      exit 0
    fi
  fi
  sleep 10
done
