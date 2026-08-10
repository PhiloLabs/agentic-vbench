#!/bin/bash
# Oracle: SuperTuxKart profile-mode telemetry for the camera-followed hero (tux),
# one row per race in video order: items, explosions, bananas, and skid_time (drift seconds).
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
      "bananas_hit": 1,
      "skid_time": 69.02
    },
    {
      "track": "snowmountain",
      "items_collected": 4,
      "times_exploded": 2,
      "bananas_hit": 3,
      "skid_time": 60.07
    },
    {
      "track": "cornfield_crossing",
      "items_collected": 4,
      "times_exploded": 2,
      "bananas_hit": 4,
      "skid_time": 40.68
    },
    {
      "track": "lighthouse",
      "items_collected": 9,
      "times_exploded": 3,
      "bananas_hit": 0,
      "skid_time": 73.35
    },
    {
      "track": "gran_paradiso_island",
      "items_collected": 6,
      "times_exploded": 1,
      "bananas_hit": 0,
      "skid_time": 92.09
    },
    {
      "track": "sandtrack",
      "items_collected": 4,
      "times_exploded": 1,
      "bananas_hit": 3,
      "skid_time": 22.67
    },
    {
      "track": "olivermath",
      "items_collected": 9,
      "times_exploded": 2,
      "bananas_hit": 1,
      "skid_time": 32.9
    },
    {
      "track": "cocoa_temple",
      "items_collected": 10,
      "times_exploded": 1,
      "bananas_hit": 0,
      "skid_time": 52.03
    },
    {
      "track": "scotland",
      "items_collected": 19,
      "times_exploded": 1,
      "bananas_hit": 0,
      "skid_time": 85.88
    },
    {
      "track": "fortmagma",
      "items_collected": 20,
      "times_exploded": 4,
      "bananas_hit": 1,
      "skid_time": 74.23
    },
    {
      "track": "ravenbridge_mansion",
      "items_collected": 4,
      "times_exploded": 1,
      "bananas_hit": 1,
      "skid_time": 44.99
    },
    {
      "track": "stk_enterprise",
      "items_collected": 22,
      "times_exploded": 3,
      "bananas_hit": 1,
      "skid_time": 39.53
    }
  ]
}
JSON
