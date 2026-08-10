#!/bin/bash
# Oracle: hero (tux) per-race items_collected + spinouts (bananas+explosions).
set -euo pipefail
OUT="${SOLUTION_PATH:-/solution/solution.json}"
mkdir -p "$(dirname "$OUT")"
cat > "$OUT" <<'JSON'
{
  "races": [
    {
      "track": "hacienda",
      "items_collected": 14,
      "spinouts": 6
    },
    {
      "track": "snowmountain",
      "items_collected": 4,
      "spinouts": 5
    },
    {
      "track": "cornfield_crossing",
      "items_collected": 4,
      "spinouts": 6
    },
    {
      "track": "lighthouse",
      "items_collected": 9,
      "spinouts": 3
    },
    {
      "track": "gran_paradiso_island",
      "items_collected": 6,
      "spinouts": 1
    },
    {
      "track": "sandtrack",
      "items_collected": 4,
      "spinouts": 4
    },
    {
      "track": "olivermath",
      "items_collected": 9,
      "spinouts": 3
    },
    {
      "track": "cocoa_temple",
      "items_collected": 10,
      "spinouts": 1
    },
    {
      "track": "scotland",
      "items_collected": 19,
      "spinouts": 1
    },
    {
      "track": "fortmagma",
      "items_collected": 20,
      "spinouts": 5
    },
    {
      "track": "ravenbridge_mansion",
      "items_collected": 4,
      "spinouts": 2
    },
    {
      "track": "stk_enterprise",
      "items_collected": 22,
      "spinouts": 4
    }
  ]
}
JSON
