#!/bin/bash
# Grade a finished run with the frozen verifier and scan its trajectory.
#
# Grading always happens on the host against steps/solve/tests/, never inside the
# run container -- the container never had the reference and must not get it.
#
# Usage: ./audit_and_grade.sh <harness> <trajectory-file>
set -euo pipefail

H="${1:?usage: ./audit_and_grade.sh <harness> <trajectory>}"
TRAJ="${2:?trajectory file required}"
TASK="$(cd "$(dirname "$0")/../.." && pwd)"
R="$(cd "$(dirname "$0")/.." && pwd)/rollouts"
SOL="$R/${H}_solution.json"

echo "=== 1. GRADE (frozen judge.py) ==="
if [ -f "$SOL" ]; then
  python3 "$TASK/steps/solve/tests/judge.py" \
    --solution "$SOL" \
    --reference "$TASK/steps/solve/tests/reference.json" \
    --output "$R/${H}_reward.json" >/dev/null
  python3 -c "
import json;d=json.load(open('$R/${H}_reward.json'))
print('  reward                ', d['reward'], '  (gate: < 0.10)')
print('  rally_discovery.f1    ', d['rally_discovery']['f1'])
print('  stroke_timing.f1      ', d['stroke_timing']['f1'])
print('  stroke_semantic_joint ', d['stroke_semantic_joint'])
print('  rally_endings.joint   ', d['rally_endings']['joint_accuracy'])
print('  reason                ', d['reason'])"
else
  echo "  no solution.json -> reward 0.0 (record as an incomplete run)"
fi

echo; echo "=== 2. LOOKUP SCAN (disqualifiers) ==="
echo "  A hit on the dataset repo, the annotation file, or a search engine voids"
echo "  the run. The harness's own model endpoint is inference, not lookup."
echo
echo "  NOTE: each harness names its search tool differently. Codex emits"
echo "  web_search, Claude Code emits WebSearch/WebFetch, and Antigravity's native"
echo "  transcript emits SEARCH_WEB / read_url_content / open_browser_url. Scanning"
echo "  for only one vendor's spelling is how a contaminated run passes an audit,"
echo "  so all three are matched here and the count is broken out per pattern."
echo
echo "--- dataset / annotation / answer-key markers (DISQUALIFIER):"
for pat in moamal01 table_tennis_data "game_2\.json" openttgames "lab\.osai\.ai" raw\.githubusercontent "reference\.json" "judge\.py"; do
  n=$(grep -c -iE "$pat" "$TRAJ" || true)
  [ "$n" != "0" ] && echo "    $pat : $n  <<< DISQUALIFIER"
done
echo "    (nothing listed above = clean)"
echo "--- web-search / browse tool invocations (DISQUALIFIER):"
# Match invocations, not mentions: the staged rules file names these tools in
# order to forbid them, so a bare substring scan reports a compliant run as dirty.
for pat in '"type"[ ]*:[ ]*"SEARCH_WEB"' '"tool_name"[ ]*:[ ]*"search_web"' "grounding-api-redirect" "vertexaisearch\\.cloud\\.google\\.com" '"name"[ ]*:[ ]*"WebSearch"' '"name"[ ]*:[ ]*"WebFetch"' '"web_search_requests"[ ]*:[ ]*[1-9]'; do
  n=$(grep -c -iE "$pat" "$TRAJ" || true)
  [ "$n" != "0" ] && echo "    $pat : $n  <<< DISQUALIFIER"
done
echo "    (nothing listed above = clean)"
echo "--- every URL the run touched (inspect: only the model endpoint is allowed):"
grep -oiE "https?://[a-z0-9._/-]+" "$TRAJ" | sort | uniq -c | sort -rn | head -20 || true

echo; echo "=== 2b. CREDENTIAL LEAK SCAN ==="
echo "  Agents can print their own environment. A Gemini run executed \`env\` and"
echo "  wrote GEMINI_API_KEY in clear text into its trajectory; injecting secrets as"
echo "  files rather than command-line arguments does not prevent this. Any hit must"
echo "  be redacted before the artifact is committed, and the key rotated."
LEAK=0
for pat in "AQ\\.[A-Za-z0-9_-]\\{20,\\}" "sk-ant-api[0-9]*-[A-Za-z0-9_-]\\{20,\\}" "sk-proj-[A-Za-z0-9_-]\\{20,\\}" "AIza[0-9A-Za-z_-]\\{30,\\}" "ghp_[A-Za-z0-9]\\{30,\\}"; do
  n=$(grep -c -E "$pat" "$TRAJ" 2>/dev/null || true)
  if [ "${n:-0}" != "0" ]; then echo "    $pat : $n  <<< SECRET IN TRAJECTORY"; LEAK=1; fi
done
for name in GEMINI_API_KEY ANTHROPIC_API_KEY OPENAI_API_KEY; do
  n=$(grep -c -E "$name=[A-Za-z0-9]" "$TRAJ" 2>/dev/null || true)
  if [ "${n:-0}" != "0" ]; then echo "    $name assigned a value : $n  <<< SECRET IN TRAJECTORY"; LEAK=1; fi
done
[ "$LEAK" = "0" ] && echo "    clean - no credential material in this trajectory"

echo; echo "=== 3. EFFORT (natural > 50 tool-call turns required) ==="
echo "  trajectory lines: $(wc -l < "$TRAJ")"
python3 - "$TRAJ" <<'PYCOUNT'
import json, sys, collections
# Each harness numbers work differently, so count with that harness's own rule and
# print the rule alongside the number; scores.md must state which one was used.
#   Codex CLI            distinct item.started of type command_execution
#   Claude Code          tool_use blocks in assistant messages
#   Antigravity native   distinct step_index whose type is a tool action
path = sys.argv[1]
# Claude turns are de-duplicated by tool_use block id: stream-json can emit the same
# assistant message more than once, and counting raw blocks inflates the number.
codex = set(); claude = set(); agy_tool = set(); agy_all = set()
AGY_TOOLS = {"RUN_COMMAND","VIEW_FILE","EDIT_FILE","CODE_ACTION","LIST_DIRECTORY","GREP","READ_FILE","WRITE_FILE"}
kinds = collections.Counter()
for line in open(path, errors="replace"):
    line = line.strip()
    if not line.startswith("{"): continue
    try: d = json.loads(line)
    except Exception: continue
    if d.get("type") == "item.started":
        it = d.get("item", {}) or {}
        if it.get("type") == "command_execution": codex.add(it.get("id"))
    if d.get("type") == "assistant":
        for c in (d.get("message", {}) or {}).get("content", []) or []:
            if c.get("type") == "tool_use": claude.add(c.get("id"))
    si = d.get("step_index")
    if si is None:
        su = d.get("step_update") or {}
        si = su.get("step_index"); ty = su.get("step_type")
    else:
        ty = d.get("type")
    if si is not None:
        agy_all.add(si); kinds[ty] += 1
        if ty in AGY_TOOLS or ty == "tool": agy_tool.add(si)
if codex:    print("  Codex rule (distinct command_execution item.started): %d" % len(codex))
if claude:   print("  Claude rule (distinct tool_use block ids): %d" % len(claude))
if agy_all:
    print("  Antigravity rule (distinct tool step_index): %d" % len(agy_tool))
    print("  all distinct step_index: %d   record types: %s" % (len(agy_all), dict(kinds.most_common(6))))
PYCOUNT
echo "  State the rule used in scores.md next to the number."

echo; echo "=== 4. NET GUARD (must have passed both before and after) ==="
tail -20 "$R/${H}.netguard.log" 2>/dev/null || echo "  no netguard log for $H"

echo; echo "=== 5. TELLTALE (manual) ==="
echo "  Gemini 3.1 Pro may skip the media and fabricate a confident answer in a"
echo "  handful of calls; 3.5 Flash may fall back to Search grounding server-side."
echo "  If the answer tracks the public annotation while missing exactly the fields"
echo "  no public record holds, or the tool-call count is implausibly low, void it."
