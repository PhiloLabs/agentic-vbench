#!/bin/bash
# Official Codex calibration run (GPT-5.6 Sol, high reasoning).
# Prereq: `codex` CLI installed + authed; ./stage_workspace.sh codex already run.
# Anti-cheat: sandboxed workspace-write (no command network), web-search tool
# disabled via config, AGENTS.md rules in workspace, raw JSONL retained.
set -euo pipefail
W=/private/tmp/avb_calib_codex
R="$(cd "$(dirname "$0")/.." && pwd)/rollouts"
mkdir -p "$R"
[ -f "$W/instruction.md" ] || { echo "run stage_workspace.sh codex first"; exit 1; }

cd "$W"
nohup codex exec --json \
  --sandbox workspace-write \
  --config model_reasoning_effort=high \
  --config tools.web_search=false \
  "$(cat instruction.md)" > "$R/codex_gpt56sol.jsonl" 2> "$R/codex_gpt56sol.err" &
PID=$!
nohup caffeinate -i -w "$PID" >/dev/null 2>&1 &
echo "codex calibration running, pid $PID"
echo "rollout: $R/codex_gpt56sol.jsonl"
echo "NOTE: record codex --version and the exact model id in scores.md."
