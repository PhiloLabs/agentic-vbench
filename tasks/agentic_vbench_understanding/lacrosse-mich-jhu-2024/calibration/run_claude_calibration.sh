#!/bin/bash
# Relaunch the official Claude Code calibration run for the lacrosse task.
# Requires: network up. Machine must stay awake until it completes (~1-2h);
# this script arms caffeinate automatically.
set -euo pipefail

W=/private/tmp/claude-501/-Users-willw-Projects-AgenticVBench/a22b957c-5064-456b-8b87-37728756ee71/scratchpad/lax_calib_claude
R=/Users/willw/Projects/AgenticVBench/tasks/lacrosse-mich-jhu-2024/calibration/rollouts
mkdir -p "$R"
rm -rf "$W/output"; mkdir -p "$W/output"   # fresh output, same materials

cd "$W"
nohup claude -p "$(cat instruction.md)" --model claude-opus-4-8 --verbose --output-format stream-json \
  --allowedTools "Bash,Read,Write,Glob,Grep" \
  --disallowedTools "WebFetch,WebSearch" \
  --append-system-prompt "This task is offline. You have no network access: never use web search or web fetch, never attempt to identify the real-world game, teams, or players, and never recall or look up any box score or public record. Work only from the pixels of the provided video and the provided files in this directory." \
  > "$R/claude_opus48.jsonl" 2> "$R/claude_opus48.err" &
PID=$!
nohup caffeinate -i -w "$PID" >/dev/null 2>&1 &
echo "calibration running, pid $PID (caffeinate armed). Rollout: $R/claude_opus48.jsonl"
