#!/bin/bash
# Oracle: write the verified event timeline as solution.json.
#
# The reference answer is the 111-event ground truth (kills/towers from the replay
# Live Client Data API, cross-checked vs the .rofl end-game aggregate; objectives
# from the post-game timeline + a second annotator; economy fields from the
# client's per-minute gold-lead series). The agent never sees this file.
#
# gt.json lives verifier-side next to judge.py; the oracle runs with the task source
# tree available, so it reads it from there and echoes it to the agent-output path.
set -euo pipefail

mkdir -p /workspace/output
GT="$(dirname "$0")/../tests/gt.json"

python3 - "$GT" <<'PY'
import json, sys
from pathlib import Path
gt = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
# Echo the events list in the exact schema the agent is asked to produce.
Path("/workspace/output/solution.json").write_text(
    json.dumps({"events": gt["events"]}, ensure_ascii=False, indent=2)
)
PY

echo "oracle: wrote /workspace/output/solution.json ($(python3 -c 'import json,sys;print(len(json.load(open("/workspace/output/solution.json"))["events"]))') events)"
