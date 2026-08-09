#!/bin/bash
# Oracle: SuperTuxKart profile-mode counts for the camera-followed hero kart (tux),
# one row per race in video order (items, explosions, bananas). Matches the hero-scoped GT.
set -euo pipefail
OUT="${SOLUTION_PATH:-/solution/solution.json}"
mkdir -p "$(dirname "$OUT")"
cat > "$OUT" <<'JSON'
{
  "races": [
    {
      "track": "hacienda",
      "items_collected": 14,
      "times_exploded": 5,
      "bananas_hit": 1
    },
    {
      "track": "snowmountain",
      "items_collected": 4,
      "times_exploded": 2,
      "bananas_hit": 3
    },
    {
      "track": "cornfield_crossing",
      "items_collected": 4,
      "times_exploded": 2,
      "bananas_hit": 4
    },
    {
      "track": "lighthouse",
      "items_collected": 9,
      "times_exploded": 3,
      "bananas_hit": 0
    },
    {
      "track": "gran_paradiso_island",
      "items_collected": 6,
      "times_exploded": 1,
      "bananas_hit": 0
    },
    {
      "track": "sandtrack",
      "items_collected": 4,
      "times_exploded": 1,
      "bananas_hit": 3
    },
    {
      "track": "olivermath",
      "items_collected": 9,
      "times_exploded": 2,
      "bananas_hit": 1
    },
    {
      "track": "cocoa_temple",
      "items_collected": 10,
      "times_exploded": 1,
      "bananas_hit": 0
    },
    {
      "track": "scotland",
      "items_collected": 19,
      "times_exploded": 1,
      "bananas_hit": 0
    },
    {
      "track": "fortmagma",
      "items_collected": 20,
      "times_exploded": 4,
      "bananas_hit": 1
    },
    {
      "track": "ravenbridge_mansion",
      "items_collected": 4,
      "times_exploded": 1,
      "bananas_hit": 1
    },
    {
      "track": "stk_enterprise",
      "items_collected": 22,
      "times_exploded": 3,
      "bananas_hit": 1
    }
  ]
}
JSON
