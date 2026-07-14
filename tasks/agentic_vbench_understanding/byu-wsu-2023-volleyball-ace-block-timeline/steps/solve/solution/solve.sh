#!/bin/bash
# Oracle: write the verified ace-and-block timeline as solution.json.
#
# The reference answer is the official NCAA rally-by-rally log (stats.ncaa.org
# contest 3241315), with block credit reconciled per player against the official
# box score. This is the verified answer key, not an echo of the input. The agent
# never sees this file.
set -euo pipefail

mkdir -p /workspace/output

python3 - <<'PY2'
import json
from pathlib import Path

EVENTS = [
  {"set": 1, "score_after": "7-7",   "type": "ace",   "players": ["Erin Livingston"]},
  {"set": 1, "score_after": "16-13", "type": "ace",   "players": ["Erin Livingston"]},
  {"set": 1, "score_after": "18-14", "type": "block", "players": ["Whitney McEwan-Llarenas", "Elyse Stowell"]},
  {"set": 1, "score_after": "18-17", "type": "block", "players": ["Argentina Ung", "Magda Jehlarova"]},
  {"set": 1, "score_after": "20-17", "type": "ace",   "players": ["Aria McComber"]},
  {"set": 2, "score_after": "1-2",   "type": "block", "players": ["Magda Jehlarova"]},
  {"set": 2, "score_after": "9-6",   "type": "block", "players": ["Kate Prior", "Mia Lee"]},
  {"set": 2, "score_after": "10-10", "type": "block", "players": ["Pia Timmer", "Lana Radakovic"]},
  {"set": 2, "score_after": "10-11", "type": "block", "players": ["Katy Ryan", "Lana Radakovic"]},
  {"set": 3, "score_after": "6-7",   "type": "block", "players": ["Lana Radakovic"]},
  {"set": 3, "score_after": "11-15", "type": "block", "players": ["Magda Jehlarova"]},
  {"set": 3, "score_after": "12-18", "type": "block", "players": ["Iman Isanovic", "Magda Jehlarova"]},
  {"set": 3, "score_after": "14-18", "type": "block", "players": ["Whitney Bower", "Whitney McEwan-Llarenas"]},
  {"set": 3, "score_after": "18-22", "type": "block", "players": ["Katy Ryan", "Lana Radakovic"]},
  {"set": 3, "score_after": "21-23", "type": "ace",   "players": ["Whitney Bower"]},
  {"set": 4, "score_after": "2-0",   "type": "block", "players": ["Whitney McEwan-Llarenas", "Erin Livingston"]},
  {"set": 4, "score_after": "6-6",   "type": "block", "players": ["Kate Prior"]},
  {"set": 4, "score_after": "6-9",   "type": "block", "players": ["Magda Jehlarova"]},
  {"set": 4, "score_after": "11-18", "type": "block", "players": ["Katy Ryan", "Magda Jehlarova"]},
  {"set": 4, "score_after": "13-18", "type": "ace",   "players": ["Whitney Bower"]},
  {"set": 4, "score_after": "16-23", "type": "block", "players": ["Eden Bower", "Whitney McEwan-Llarenas"]},
  {"set": 4, "score_after": "17-23", "type": "block", "players": ["Eden Bower"]},
  {"set": 4, "score_after": "18-23", "type": "block", "players": ["Kate Prior", "Whitney McEwan-Llarenas"]},
  {"set": 4, "score_after": "19-25", "type": "block", "players": ["Argentina Ung", "Lana Radakovic"]},
]

Path("/workspace/output/solution.json").write_text(json.dumps({"events": EVENTS}, indent=2))
PY2

echo "oracle: wrote /workspace/output/solution.json (24 events)"
