#!/bin/bash
# Oracle: write the verified block timeline as solution.json.
#
# The reference answer is the official NCAA rally-by-rally log (stats.ncaa.org
# contest 3241315). Block credit is reconciled per player against the official box
# score; each block's `blocked` hitter is the opposing attacker on the "Attack by X"
# line immediately preceding the "Block by ..." rally (direction-verified). This is
# the verified answer key, not an echo of the input. The agent never sees this file.
set -euo pipefail

mkdir -p /workspace/output

python3 - <<'PY2'
import json
from pathlib import Path

EVENTS = [
  {"set": 1, "score_after": "18-14",     "type": "block", "players": ["Whitney McEwan-Llarenas", "Elyse Stowell"],              "blocked": "Katy Ryan", "setter": "Argentina Ung"},
  {"set": 1, "score_after": "18-17",     "type": "block", "players": ["Argentina Ung", "Magda Jehlarova"],                      "blocked": "Elyse Stowell", "setter": "Whitney Bower"},
  {"set": 2, "score_after": "9-6",       "type": "block", "players": ["Kate Prior", "Mia Lee"],                                 "blocked": "Iman Isanovic", "setter": "Argentina Ung"},
  {"set": 2, "score_after": "10-10",     "type": "block", "players": ["Pia Timmer", "Lana Radakovic"],                          "blocked": "Kate Prior", "setter": "Whitney Bower"},
  {"set": 2, "score_after": "10-11",     "type": "block", "players": ["Katy Ryan", "Lana Radakovic"],                           "blocked": "Elyse Stowell", "setter": "Whitney Bower"},
  {"set": 3, "score_after": "6-7",       "type": "block", "players": ["Lana Radakovic"],                                        "blocked": "Erin Livingston", "setter": "Whitney Bower"},
  {"set": 3, "score_after": "11-15",     "type": "block", "players": ["Magda Jehlarova"],                                       "blocked": "Mia Lee", "setter": "Whitney Bower"},
  {"set": 3, "score_after": "12-18",     "type": "block", "players": ["Iman Isanovic", "Magda Jehlarova"],                      "blocked": "Kate Prior", "setter": "Whitney Bower"},
  {"set": 3, "score_after": "14-18",     "type": "block", "players": ["Whitney Bower", "Whitney McEwan-Llarenas"],              "blocked": "Iman Isanovic", "setter": "Argentina Ung"},
  {"set": 3, "score_after": "18-22",     "type": "block", "players": ["Katy Ryan", "Lana Radakovic"],                           "blocked": "Erin Livingston", "setter": "Whitney Bower"},
  {"set": 4, "score_after": "2-0",       "type": "block", "players": ["Whitney McEwan-Llarenas", "Erin Livingston"],            "blocked": "Iman Isanovic", "setter": "Karly Basham"},
  {"set": 4, "score_after": "6-6",       "type": "block", "players": ["Kate Prior"],                                            "blocked": "Pia Timmer", "setter": "Karly Basham"},
  {"set": 4, "score_after": "6-9",       "type": "block", "players": ["Magda Jehlarova"],                                       "blocked": "Mia Lee", "setter": "Whitney Bower"},
  {"set": 4, "score_after": "11-18",     "type": "block", "players": ["Katy Ryan", "Magda Jehlarova"],                          "blocked": "Erin Livingston", "setter": "Whitney Bower"},
  {"set": 4, "score_after": "16-23",     "type": "block", "players": ["Eden Bower", "Whitney McEwan-Llarenas"],                 "blocked": "Magda Jehlarova", "setter": "Argentina Ung"},
  {"set": 4, "score_after": "17-23",     "type": "block", "players": ["Eden Bower"],                                            "blocked": "Magda Jehlarova", "setter": "Argentina Ung"},
  {"set": 4, "score_after": "18-23",     "type": "block", "players": ["Kate Prior", "Whitney McEwan-Llarenas"],                 "blocked": "Iman Isanovic", "setter": "Karly Basham"},
  {"set": 4, "score_after": "19-25",     "type": "block", "players": ["Argentina Ung", "Lana Radakovic"],                       "blocked": "Eden Bower", "setter": "Whitney Bower"},
]
for e in EVENTS:
    if e.get("blocked") is None:
        e.pop("blocked", None)

Path("/workspace/output/solution.json").write_text(json.dumps({"events": EVENTS}, indent=2))
PY2

echo "oracle: wrote /workspace/output/solution.json (18 block points)"
