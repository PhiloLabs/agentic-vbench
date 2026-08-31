#!/bin/bash
# single_frame anti-shortcut ablation: give a strong agent ONE representative frame and the task
# instruction, and score its answer with the task judge. The family requires this to be <= 0.15 —
# a task that can be answered from one frame is not testing ordered event reconstruction.
#
#   ablate_single_frame.sh VIDEO TASK_DIR OUTDIR [AT_SECONDS]
set -euo pipefail
VIDEO=${1:?video}; TASK=${2:?task}; OUT=${3:?out}; AT=${4:-570}   # ~mid-video by default
mkdir -p "$OUT/materials" "$OUT/output"
FF=$(/usr/bin/python3 -c "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())")
"$FF" -v error -ss "$AT" -i "$VIDEO" -frames:v 1 "$OUT/materials/frame.png" -y
{
  cat "$TASK/steps/solve/instruction.md"
  cat <<'EOP'

## THIS RUN IS DELIBERATELY DEGRADED (single-frame ablation)

You are given exactly ONE still frame at `materials/frame.png` instead of the video — there is no
video file and no ffmpeg. Reconstruct as much of the ordered event ledger as you honestly can from
this single frame and write it to `output/solution.json` in the schema above. Do not invent events
you cannot see; guessing a plausible sequence is not the task.
EOP
} > "$OUT/prompt.md"
cd "$OUT"
timeout 1800s codex exec --dangerously-bypass-approvals-and-sandbox \
  "$(cat "$OUT/prompt.md")" > "$OUT/codex.log" 2>&1 < /dev/null || true
[ -s "$OUT/output/solution.json" ] || echo '{"events": []}' > "$OUT/output/solution.json"
/usr/bin/python3 "$TASK/steps/solve/tests/judge.py" --solution "$OUT/output/solution.json" \
  --reward-json "$OUT/reward.json" --reward-txt "$OUT/reward.txt"
echo "single_frame reward:"; cat "$OUT/reward.txt"
