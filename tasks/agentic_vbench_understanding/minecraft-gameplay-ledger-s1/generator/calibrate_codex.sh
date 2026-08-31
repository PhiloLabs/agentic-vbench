#!/bin/bash
# Run one Codex calibration rollout against a rendered session and score it with the task's own
# judge. This is the harness the difficulty numbers in calibration/scores.md come from.
#
#   calibrate_codex.sh VIDEO TASK_DIR OUTDIR [HOURS]
#
# Protocol notes, each of which cost a wasted run:
#   * `< /dev/null` on the codex invocation. Nested quoting once ate stdin and the agent sat with no
#     prompt at all, producing a "timeout" that was really a launch bug.
#   * a generous wall clock (default 2.5 h). A 55-minute cap timed out at 42 turns having written
#     NOTHING, so the run scored 0 for reasons that had nothing to do with task difficulty.
#   * the prompt tells the agent to write a first ledger early and refine it, so a timeout degrades
#     to a partial answer instead of an empty one.
#   * turns and tokens are read from Codex's own session JSONL, not estimated. An earlier writeup
#     said "~50 tool calls" when the true count was 17.
#   * the score is produced by the TASK'S judge.py against the TASK'S ground_truth.json. Never
#     re-score an old rollout under a new scorer and report it as a new measurement: the rollout was
#     produced against different targets, so the number is meaningless.
set -euo pipefail
VIDEO=${1:?video}
TASK=${2:?task dir}
OUT=${3:?outdir}
HOURS=${4:-2.5}

[ -s "$VIDEO" ] || { echo "FAIL no video $VIDEO"; exit 2; }
[ -s "$TASK/steps/solve/tests/judge.py" ] || { echo "FAIL no judge in $TASK"; exit 2; }
mkdir -p "$OUT"/{materials,output}
# hard-link if possible: the video is ~285 MB and copying it per rollout is pure waste
ln "$VIDEO" "$OUT/materials/game.mp4" 2>/dev/null || cp "$VIDEO" "$OUT/materials/game.mp4"

{
  cat "$TASK/steps/solve/instruction.md"
  cat <<'EOP'

## Practical notes for this run

* The video is at `materials/game.mp4` (relative to your working directory).
* Write your answer to `output/solution.json`.
* Write a first complete `output/solution.json` EARLY — after your first pass through the video —
  and then refine it. Do not leave it unwritten while you analyse; a partial ledger is worth far
  more than none.
* `ffmpeg` and `ffprobe` are available for seeking and sampling frames.
EOP
} > "$OUT/prompt.md"

echo "=== codex exec starting ($(date -u +%H:%M:%SZ), budget ${HOURS}h) ==="
SECS=$(/usr/bin/python3 -c "print(int(float('$HOURS')*3600))")
cd "$OUT"
set +e
timeout "${SECS}s" codex exec --dangerously-bypass-approvals-and-sandbox \
  "$(cat "$OUT/prompt.md")" > "$OUT/codex.log" 2>&1 < /dev/null
CODEX_RC=$?
set -e
echo "codex exit=$CODEX_RC"

if [ ! -s "$OUT/output/solution.json" ]; then
  echo "NO_SOLUTION_WRITTEN — recording as a run that produced nothing"
  echo '{"events": []}' > "$OUT/output/solution.json"
fi

/usr/bin/python3 "$TASK/steps/solve/tests/judge.py" \
  --solution "$OUT/output/solution.json" \
  --reward-json "$OUT/reward.json" --reward-txt "$OUT/reward.txt"
echo "=== reward ==="; cat "$OUT/reward.json"

# turns and tokens, from Codex's own session record
/usr/bin/python3 - "$OUT" <<'PY'
import glob, json, os, sys
out = sys.argv[1]
sessions = sorted(glob.glob(os.path.expanduser("~/.codex/sessions/**/*.jsonl"), recursive=True),
                  key=os.path.getmtime)
if not sessions:
    print("no codex session jsonl found — turns/tokens unavailable"); raise SystemExit
path = sessions[-1]
turns = tin = tout = 0
for line in open(path, errors="replace"):
    try: rec = json.loads(line)
    except Exception: continue
    blob = json.dumps(rec)
    if '"function_call"' in blob or '"tool_use"' in blob:
        turns += 1
    usage = rec.get("payload", {}).get("info", {}).get("total_token_usage") or {}
    if usage:
        tin, tout = usage.get("input_tokens", tin), usage.get("output_tokens", tout)
print(f"session={os.path.basename(path)} tool_calls={turns} input_tokens={tin} output_tokens={tout} total={tin+tout}")
open(os.path.join(out, "usage.txt"), "w").write(
    f"tool_calls={turns}\ninput_tokens={tin}\noutput_tokens={tout}\ntotal={tin+tout}\nsession={path}\n")
PY
echo "CALIBRATION_DONE $OUT"
