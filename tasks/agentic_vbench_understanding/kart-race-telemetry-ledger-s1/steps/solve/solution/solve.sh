#!/bin/bash
# Oracle: SuperTuxKart profile-mode counts for the camera-followed hero kart (tux),
# one row per race in video order. Matches the hero-scoped ground truth; judge.py scores 1.0.
set -euo pipefail
OUT="${SOLUTION_PATH:-/solution/solution.json}"
mkdir -p "$(dirname "$OUT")"
cat > "$OUT" <<'JSON'
{
  "races": [
    {
      "track": "hacienda",
      "items_collected": 12,
      "times_exploded": 1
    },
    {
      "track": "snowmountain",
      "items_collected": 6,
      "times_exploded": 2
    },
    {
      "track": "cornfield_crossing",
      "items_collected": 3,
      "times_exploded": 1
    },
    {
      "track": "lighthouse",
      "items_collected": 7,
      "times_exploded": 0
    },
    {
      "track": "gran_paradiso_island",
      "items_collected": 8,
      "times_exploded": 2
    },
    {
      "track": "sandtrack",
      "items_collected": 6,
      "times_exploded": 2
    },
    {
      "track": "black_forest",
      "items_collected": 30,
      "times_exploded": 0
    },
    {
      "track": "cocoa_temple",
      "items_collected": 14,
      "times_exploded": 4
    }
  ]
}
JSON
