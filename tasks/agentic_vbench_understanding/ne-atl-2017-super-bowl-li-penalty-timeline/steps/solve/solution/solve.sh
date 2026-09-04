#!/bin/bash
# Oracle: write the verified referee-announced player-foul timeline as solution.json.
#
# The reference answer is the official NFL Game Book penalty summary (cross-checked on
# nflpenalties.com), restricted by the task's scope rule to fouls with an announced
# jersey number. Like the Assembly/basketball oracles, this is the verified answer key,
# not an echo of the input. The agent never sees this file.
#
# The list is the full set of referee-announced player fouls from the official NFL Game
# Book, kept in lockstep with GROUND_TRUTH in ../tests/judge.py. Scope rule and exclusions
# are documented in ../../../PROVENANCE.md.
set -euo pipefail

mkdir -p /workspace/output

python3 - <<'PY'
import json
from pathlib import Path

PENALTIES = [
    {"quarter": 1, "clock": "13:47", "type": "offensive holding",           "player_number": 55, "team": "ATL"},
    {"quarter": 2, "clock": "14:19", "type": "offensive holding",           "player_number": 88, "team": "NE"},
    {"quarter": 2, "clock": "8:55",  "type": "defensive pass interference", "player_number": 23, "team": "NE"},
    {"quarter": 2, "clock": "8:02",  "type": "defensive holding",           "player_number": 23, "team": "ATL"},
    {"quarter": 2, "clock": "6:10",  "type": "defensive holding",           "player_number": 34, "team": "ATL"},
    {"quarter": 2, "clock": "5:16",  "type": "defensive holding",           "player_number": 34, "team": "ATL"},
    {"quarter": 2, "clock": "0:18",  "type": "offensive holding",           "player_number": 88, "team": "NE"},
    {"quarter": 3, "clock": "13:02", "type": "offensive pass interference", "player_number": 15, "team": "NE"},
    {"quarter": 3, "clock": "8:43",  "type": "defensive pass interference", "player_number": 21, "team": "NE"},
    {"quarter": 3, "clock": "1:30",  "type": "offensive holding",           "player_number": 70, "team": "ATL"},
    {"quarter": 4, "clock": "3:50",  "type": "offensive holding",           "player_number": 70, "team": "ATL"},
    {"quarter": 4, "clock": "0:57",  "type": "defensive offside",           "player_number": 93, "team": "ATL"},
    {"quarter": 5, "clock": "11:18", "type": "defensive pass interference", "player_number": 59, "team": "ATL"},
]

Path("/workspace/output/solution.json").write_text(json.dumps({"penalties": PENALTIES}, indent=2))
PY

echo "oracle: wrote /workspace/output/solution.json (13 referee-announced player fouls)"
