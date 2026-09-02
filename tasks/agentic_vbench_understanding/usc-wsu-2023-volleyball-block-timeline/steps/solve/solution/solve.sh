#!/bin/bash
# Oracle: write the verified block-point timeline as solution.json.
#
# The reference answer is the official NCAA rally-by-rally log (stats.ncaa.org
# contest 3252428, #25 USC at #9 Washington State, 2023-11-12). Block credit is
# reconciled per player against the official box score; each block's `blocked` hitter
# is the opposing attacker on the "Attack by X" line immediately preceding the
# terminal "Block by ..." rally (direction-verified). This is the verified answer
# key, not an echo of the input. The agent never sees this file.
set -euo pipefail

mkdir -p /workspace/output

python3 - <<'PY2'
import json
from pathlib import Path

EVENTS = [
  {"set": 1, "score_after": "4-2",       "type": "block", "players": ["Mia Tuaniga", "Lindsey Miller"],                         "blocked": "Iman Isanovic"},
  {"set": 1, "score_after": "14-10",     "type": "block", "players": ["Lindsey Miller"],                                        "blocked": "Magda Jehlarova"},
  {"set": 1, "score_after": "23-15",     "type": "block", "players": ["Tyrah Ariail", "Kalyah Williams"],                       "blocked": "Katy Ryan"},
  {"set": 1, "score_after": "25-15",     "type": "block", "players": ["Kalyah Williams", "Tyrah Ariail"],                       "blocked": "Iman Isanovic"},
  {"set": 2, "score_after": "2-1",       "type": "block", "players": ["Lindsey Miller", "Skylar Fields"],                       "blocked": "Pia Timmer"},
  {"set": 2, "score_after": "10-7",      "type": "block", "players": ["Tyrah Ariail"],                                          "blocked": "Katy Ryan"},
  {"set": 2, "score_after": "16-10",     "type": "block", "players": ["Magda Jehlarova", "Argentina Ung"],                      "blocked": "Skylar Fields"},
  {"set": 3, "score_after": "1-6",       "type": "block", "players": ["Magda Jehlarova", "Argentina Ung"],                      "blocked": "Skylar Fields"},
  {"set": 3, "score_after": "4-7",       "type": "block", "players": ["London Wijay", "Lindsey Miller"],                        "blocked": "Magda Jehlarova"},
  {"set": 3, "score_after": "7-10",      "type": "block", "players": ["Tyrah Ariail"],                                          "blocked": "Iman Isanovic"},
  {"set": 3, "score_after": "13-17",     "type": "block", "players": ["Magda Jehlarova", "Argentina Ung"],                      "blocked": "London Wijay"},
  {"set": 3, "score_after": "16-25",     "type": "block", "players": ["Magda Jehlarova"],                                       "blocked": "Tyrah Ariail"},
  {"set": 4, "score_after": "1-1",       "type": "block", "players": ["Katy Ryan", "Magda Jehlarova"],                          "blocked": "Skylar Fields"},
  {"set": 4, "score_after": "3-3",       "type": "block", "players": ["Magda Jehlarova", "Argentina Ung"],                      "blocked": "Skylar Fields"},
  {"set": 4, "score_after": "7-5",       "type": "block", "players": ["Lana Radakovic", "Argentina Ung"],                       "blocked": "London Wijay"},
  {"set": 4, "score_after": "10-8",      "type": "block", "players": ["Katy Ryan", "Lana Radakovic"],                           "blocked": "London Wijay"},
  {"set": 4, "score_after": "16-17",     "type": "block", "players": ["Pia Timmer"],                                            "blocked": "Skylar Fields"},
  {"set": 4, "score_after": "19-20",     "type": "block", "players": ["Katy Ryan", "Magda Jehlarova"],                          "blocked": "Kalyah Williams"},
  {"set": 5, "score_after": "3-3",       "type": "block", "players": ["Magda Jehlarova", "Iman Isanovic"],                      "blocked": "Kalyah Williams"},
  {"set": 5, "score_after": "3-7",       "type": "block", "players": ["Magda Jehlarova", "Argentina Ung"],                      "blocked": "Skylar Fields"},
  {"set": 5, "score_after": "5-8",       "type": "block", "players": ["Mia Tuaniga", "Rylie McGinest"],                         "blocked": "Pia Timmer"},
  {"set": 5, "score_after": "5-11",      "type": "block", "players": ["Argentina Ung"],                                         "blocked": "London Wijay"},
  {"set": 5, "score_after": "10-14",     "type": "block", "players": ["Tyrah Ariail", "London Wijay"],                          "blocked": "Iman Isanovic"},
]
for e in EVENTS:
    if e.get("blocked") is None:
        e.pop("blocked", None)

Path("/workspace/output/solution.json").write_text(json.dumps({"events": EVENTS}, indent=2))
PY2

echo "oracle: wrote /workspace/output/solution.json (23 block points)"
