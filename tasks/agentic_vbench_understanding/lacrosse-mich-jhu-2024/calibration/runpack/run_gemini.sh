#!/bin/bash
# Official Antigravity/Gemini calibration run.
# Usage: ./run_gemini.sh [gemini-3.5-flash|gemini-3.1-pro]   (default 3.5-flash;
# run BOTH models per the site's requirements when possible.)
# Prereq: `agy` CLI installed + authed; ./stage_workspace.sh gemini already run.
#
# Anti-cheat (the #54 volleyball-thread Gemini playbook, applied in full):
#  1. GEMINI.md rules file in the workspace bans all web/search grounding.
#  2. Workspace is outside any repo; no key/GT reachable (stage script guards).
#  3. WIPE CONVERSATION STORES FIRST — Antigravity keeps a cross-conversation
#     SQLite memory; a prior session about this task could leak. This script
#     moves any existing store aside before launching.
#  4. Raw log retained; audit_and_grade.sh scans it for grounding/lookup marks.
#  5. Post-run telltale check: public-record-ish fields right + unrecorded
#     fields wrong in FEW tool calls = answered from memory/search, void run.
set -euo pipefail
MODEL="${1:-gemini-3.5-flash}"
W=/private/tmp/avb_calib_gemini
R="$(cd "$(dirname "$0")/.." && pwd)/rollouts"
mkdir -p "$R"
[ -f "$W/instruction.md" ] || { echo "run stage_workspace.sh gemini first"; exit 1; }

# (3) move conversation stores aside (locations vary by version — best effort)
TS=$(date +%s)
for d in "$HOME/.antigravity" "$HOME/Library/Application Support/Antigravity" \
         "$HOME/.config/antigravity"; do
  [ -e "$d" ] && mv "$d" "${d}.pre_calib_${TS}" && echo "moved aside: $d"
done

SAFE_MODEL=$(echo "$MODEL" | tr '.' '_')
cd "$W"
nohup agy -p "$(cat instruction.md)" --model "$MODEL" \
  --log-file "$R/antigravity_${SAFE_MODEL}.log" \
  > "$R/antigravity_${SAFE_MODEL}.out" 2> "$R/antigravity_${SAFE_MODEL}.err" &
PID=$!
nohup caffeinate -i -w "$PID" >/dev/null 2>&1 &
echo "antigravity ($MODEL) running, pid $PID"
echo "log: $R/antigravity_${SAFE_MODEL}.log"
echo "NOTE: record agy --version + exact model id in scores.md; restore the"
echo "conversation stores after calibration if you use Antigravity personally."
