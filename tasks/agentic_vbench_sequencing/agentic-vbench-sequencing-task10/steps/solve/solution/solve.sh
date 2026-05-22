#!/bin/bash
# Oracle: writes the ground-truth solution.json AND solution.mp4 (concat
# of the correct narrative order). Failure-loud: re-encode fallback if
# stream-copy concat fails on codec-mismatched clips.
set -euo pipefail

mkdir -p /workspace/output /workspace/work

python3 - <<'PY'
import json, subprocess, sys
from pathlib import Path

CORRECT = ['13', '5', '8', '7', '10', '3', '11', '14', '6', '15', '9', '1', '4', '2', '12']
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

copy_cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(list_file), "-c", "copy",
            "/workspace/output/solution.mp4"]
r = subprocess.run(copy_cmd, capture_output=True)
if r.returncode != 0:
    print("stream-copy concat failed, falling back to re-encode", file=sys.stderr)
    print(r.stderr.decode()[-400:], file=sys.stderr)
    reenc_cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                 "-i", str(list_file),
                 "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                 "-c:a", "aac", "-b:a", "192k",
                 "/workspace/output/solution.mp4"]
    subprocess.run(reenc_cmd, check=True)
PY

echo "oracle: wrote /workspace/output/solution.json + solution.mp4"
