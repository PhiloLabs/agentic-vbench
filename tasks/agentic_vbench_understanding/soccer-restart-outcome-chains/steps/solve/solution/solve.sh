#!/bin/bash
# Oracle: write the verified restart-outcome timeline as solution.json.
#
# The reference answer is a deterministic transform of SoccerNet-v2's published,
# multi-annotator Labels-v2.json for this match (see ../../../provenance/build_gt.py):
# every visible ball restart with its clip time, restart type, taking team, and the
# outcome of the ensuing play. This is the verified answer key, not an echo of the
# input, and the agent never sees this file. The times mirror judge.py's GROUND_TRUTH.
set -euo pipefail

mkdir -p /workspace/output

python3 - <<'PYEOF'
import json
from pathlib import Path

RESTARTS = [
  {"t": 36.171, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 255.898, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 314.496, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 455.242, "restart_type": 4, "team": "home", "outcome": 0},
  {"t": 478.831, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 572.604, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 678.191, "restart_type": 4, "team": "home", "outcome": 0},
  {"t": 800.305, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 827.71, "restart_type": 2, "team": "home", "outcome": 0},
  {"t": 907.559, "restart_type": 4, "team": "away", "outcome": 0},
  {"t": 994.675, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 1229.914, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 1265.495, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 1299.418, "restart_type": 4, "team": "away", "outcome": 0},
  {"t": 1361.803, "restart_type": 3, "team": "away", "outcome": 1},
  {"t": 1523.462, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 1550.744, "restart_type": 4, "team": "home", "outcome": 0},
  {"t": 1674.561, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 1697.925, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 1768.753, "restart_type": 2, "team": "away", "outcome": 0},
  {"t": 1789.38, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 1831.929, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 1852.939, "restart_type": 1, "team": "home", "outcome": 1},
  {"t": 2013.876, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 2058.524, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 2312.689, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 2323.566, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 2342.905, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 2518.78, "restart_type": 4, "team": "home", "outcome": 0},
  {"t": 2541.112, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 2587.209, "restart_type": 2, "team": "away", "outcome": 1},
  {"t": 2619.248, "restart_type": 2, "team": "away", "outcome": 1},
  {"t": 2679.026, "restart_type": 4, "team": "away", "outcome": 0},
  {"t": 2739.665, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 2746.51, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 2881.81, "restart_type": 4, "team": "home", "outcome": 0},
  {"t": 2911.357, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 2949.002, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 2964.613, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 2984.139, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 3121.791, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 3169.752, "restart_type": 3, "team": "home", "outcome": 1},
  {"t": 3207.901, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 3286.212, "restart_type": 4, "team": "away", "outcome": 0},
  {"t": 3331.83, "restart_type": 2, "team": "home", "outcome": 1},
  {"t": 3386.185, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 3403.086, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 3429.644, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 3459.781, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 3482.832, "restart_type": 4, "team": "home", "outcome": 0},
  {"t": 3512.341, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 3569.955, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 3578.975, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 3594.814, "restart_type": 1, "team": "away", "outcome": 1},
  {"t": 3640.861, "restart_type": 2, "team": "away", "outcome": 1},
  {"t": 3701.565, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 3770.962, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 3984.571, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 4000.584, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 4063.635, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 4129.846, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 4147.889, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 4180.445, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 4186.105, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 4238.853, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 4299.588, "restart_type": 1, "team": "home", "outcome": 1},
  {"t": 4325.987, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 4467.823, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 4548.551, "restart_type": 4, "team": "home", "outcome": 0},
  {"t": 4615.747, "restart_type": 4, "team": "home", "outcome": 0},
  {"t": 4645.91, "restart_type": 1, "team": "away", "outcome": 1},
  {"t": 4698.201, "restart_type": 4, "team": "away", "outcome": 0},
  {"t": 4743.767, "restart_type": 4, "team": "away", "outcome": 0},
  {"t": 4757.489, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 4809.703, "restart_type": 4, "team": "home", "outcome": 0},
  {"t": 4920.136, "restart_type": 3, "team": "away", "outcome": 2},
  {"t": 5046.555, "restart_type": 4, "team": "away", "outcome": 0},
  {"t": 5187.961, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 5242.864, "restart_type": 3, "team": "away", "outcome": 0},
  {"t": 5307.401, "restart_type": 4, "team": "home", "outcome": 0},
  {"t": 5387.647, "restart_type": 1, "team": "home", "outcome": 0},
]

Path("/workspace/output/solution.json").write_text(
    json.dumps({"sequence": RESTARTS}, indent=2))
PYEOF

echo "oracle: wrote /workspace/output/solution.json (81 restarts)"
