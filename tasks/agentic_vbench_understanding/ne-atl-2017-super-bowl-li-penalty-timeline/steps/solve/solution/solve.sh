#!/bin/bash
# Oracle: write the verified referee-announced player-foul timeline as solution.json.
#
# The reference answer is the official NFL Game Book penalty summary (cross-checked on
# nflpenalties.com), restricted by the task's scope rule to fouls with an announced
# jersey number. Like the Assembly/basketball oracles, this is the verified answer key,
# not an echo of the input. The agent never sees this file.
#
# NOTE: this is the PILOT subset — the four fouls whose announced jersey numbers were
# verified by transcribing the broadcast audio. The full-game oracle (every referee
# announcement, per maintainer guidance) is pending an official Game Book parse and will
# replace this list, in lockstep with GROUND_TRUTH in ../tests/judge.py, before calibration.
set -euo pipefail

mkdir -p /workspace/output

python3 - <<'PY'
import json
from pathlib import Path

PENALTIES = [
    {"quarter": 2, "clock": "8:02",  "type": "defensive holding",           "player_number": 23, "team": "ATL"},
    {"quarter": 2, "clock": "5:16",  "type": "defensive holding",           "player_number": 34, "team": "ATL"},
    {"quarter": 3, "clock": "1:30",  "type": "offensive holding",           "player_number": 70, "team": "ATL"},
    {"quarter": 5, "clock": "11:18", "type": "defensive pass interference", "player_number": 59, "team": "ATL"},
]

Path("/workspace/output/solution.json").write_text(json.dumps({"penalties": PENALTIES}, indent=2))
PY

echo "oracle: wrote /workspace/output/solution.json (pilot subset: 4 fouls)"
