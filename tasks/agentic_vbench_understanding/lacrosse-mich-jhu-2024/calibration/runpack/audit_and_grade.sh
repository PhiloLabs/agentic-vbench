#!/bin/bash
# Grade a finished calibration run and scan its trajectory for cheating.
# Usage: ./audit_and_grade.sh codex|gemini <trajectory-file>
set -euo pipefail
H="${1:?usage: audit_and_grade.sh codex|gemini <trajectory>}"
TRAJ="${2:?trajectory file required}"
W="/private/tmp/avb_calib_${H}"
TASK="$(cd "$(dirname "$0")/../.." && pwd)"

echo "=== 1. GRADE ==="
if [ -f "$W/output/solution.json" ]; then
  python3 "$TASK/steps/solve/tests/verify.py" "$W/output/solution.json" \
          "$TASK/steps/solve/tests/answer_key.json"
else
  echo "NO solution.json -> reward 0.0 (record as failed/incomplete run)"
fi

echo; echo "=== 2. CHEAT SCAN ==="
echo "Disqualifiers are a real LOOKUP (web search / box-score fetch) or answer-key"
echo "access. Reading/naming the on-screen team names off the jerseys is NOT a"
echo "violation — no_media=0.0 proves identity alone yields nothing — so identity"
echo "mentions are reported below as CONTEXT, not as a void trigger."
echo "--- web-LOOKUP markers (DISQUALIFIER — a real external fetch):"
grep -c -iE "web_search|websearch|webfetch|search.grounding|stats\.ncaa|ncaa\.com|espn\.com|google\.com/search" "$TRAJ" || true
echo "    (inspect the actual URLs — the solver's own model API endpoint, e.g."
echo "     chatgpt.com/backend-api or generativelanguage.googleapis, is inference,"
echo "     NOT a lookup, and does not count):"
grep -oiE "https?://[a-z0-9._/-]+" "$TRAJ" | sort | uniq -c || true
echo "--- answer-key/grader access (DISQUALIFIER):"
grep -c -iE "answer_key|ground_truth|/tests/|verify\.py" "$TRAJ" || true
echo "--- game-identity mentions (CONTEXT ONLY — not a violation by itself):"
grep -c -iE "michigan|hopkins|jhu|homewood|wolverines|blue jays|mgoblue|hopkinssports" "$TRAJ" || true

echo; echo "=== 3. EFFORT (natural >50 tool calls required) ==="
echo "trajectory lines: $(wc -l < "$TRAJ")"
echo "rough tool-call markers:"
grep -c -iE '"type": ?"(tool_use|function_call|tool_call)"|exec_command|shell_call' "$TRAJ" || true

echo; echo "=== 4. TELLTALE (manual): if the ledger's team-split/score is close"
echo "to the real game but scorers/order are wrong AND tool calls are few, the"
echo "run answered from memory -> VOID. Compare details in scores.md. ==="
