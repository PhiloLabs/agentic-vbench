#!/bin/bash
# Oracle: writes the ground-truth solution.json directly.
set -euo pipefail

mkdir -p /workspace/output

python3 - <<'PY'
import json, subprocess
from pathlib import Path

CORRECT = ['15', '11', '17', '7', '1', '10', '4', '16', '12', '2', '5', '9', '18', '6', '3', '8', '14', '13']
materials = Path("/workspace/materials")

def duration(p):
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(p),
    ]).decode().strip()
    return float(out)

durs = {c: duration(materials / f"{c}.mp4") for c in CORRECT}

t = 0.0
segments = []
for c in CORRECT:
    d = durs[c]
    segments.append({
        "output": [round(t, 3), round(t + d, 3)],
        "source": c,
        "source_range": [0.0, round(d, 3)],
    })
    t += d

Path("/workspace/output/solution.json").write_text(
    json.dumps({"segments": segments}, indent=2)
)

list_file = Path("/workspace/work/concat.txt")
list_file.parent.mkdir(parents=True, exist_ok=True)
list_file.write_text(
    "\n".join(f"file '{materials / f'{c}.mp4'}'" for c in CORRECT) + "\n"
)

subprocess.run([
    "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
    "-c", "copy", "/workspace/output/solution.mp4",
], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
PY

echo "oracle: wrote /workspace/output/solution.json and (best-effort) solution.mp4"
