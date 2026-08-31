#!/bin/bash
# Oracle: write the verified right-hand 3D joint trajectory as solution.json.
#
# The reference answer is the capture rig's logged hand-tracking, forward-kinematicked
# to 20 canonical joints and expressed in each clip's RGB camera frame. It ships on the
# verifier side and is copied to /solution only for this oracle step, so the agent never
# sees it. This is the verified answer key, not something read from the clips.
set -euo pipefail

mkdir -p /workspace/output

python3 - <<'PY'
import json
from pathlib import Path

gt = json.loads(Path("/solution/ground_truth.json").read_text())
clips = {}
for clip in gt["clips"]:
    clips[clip["clip"]] = [
        {"frame": q["frame"], "joints_m": q["joints_m"]} for q in clip["queries"]
    ]
Path("/workspace/output/solution.json").write_text(json.dumps({"clips": clips}, indent=2))
PY

n=$(python3 -c "import json;d=json.load(open('/workspace/output/solution.json'));print(sum(len(v) for v in d['clips'].values()))")
echo "oracle: wrote /workspace/output/solution.json (${n} query frames)"
