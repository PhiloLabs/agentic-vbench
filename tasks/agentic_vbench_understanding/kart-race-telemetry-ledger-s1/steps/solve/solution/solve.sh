#!/bin/bash
# Oracle: hero (tux) per-race counts + skid_time (VIDEO seconds), each tagged with its video time t.
set -euo pipefail
OUT="${SOLUTION_PATH:-/solution/solution.json}"
mkdir -p "$(dirname "$OUT")"
cat > "$OUT" <<'JSON'
{
  "races": [
    {
      "track": "hacienda",
      "t": 113.3,
      "items_collected": 17,
      "spinouts": 3,
      "skid_time": 85.3
    },
    {
      "track": "snowmountain",
      "t": 345.1,
      "items_collected": 14,
      "spinouts": 2,
      "skid_time": 74.87
    },
    {
      "track": "cornfield_crossing",
      "t": 632.7,
      "items_collected": 6,
      "spinouts": 10,
      "skid_time": 62.62
    },
    {
      "track": "lighthouse",
      "t": 906.9,
      "items_collected": 13,
      "spinouts": 1,
      "skid_time": 96.52
    },
    {
      "track": "gran_paradiso_island",
      "t": 1221.8,
      "items_collected": 22,
      "spinouts": 1,
      "skid_time": 171.05
    },
    {
      "track": "sandtrack",
      "t": 1559.5,
      "items_collected": 8,
      "spinouts": 2,
      "skid_time": 29.34
    },
    {
      "track": "olivermath",
      "t": 1749.9,
      "items_collected": 10,
      "spinouts": 1,
      "skid_time": 37.04
    },
    {
      "track": "cocoa_temple",
      "t": 1992.7,
      "items_collected": 15,
      "spinouts": 4,
      "skid_time": 81.95
    },
    {
      "track": "scotland",
      "t": 2297.0,
      "items_collected": 13,
      "spinouts": 0,
      "skid_time": 117.07
    },
    {
      "track": "fortmagma",
      "t": 2548.3,
      "items_collected": 16,
      "spinouts": 5,
      "skid_time": 94.56
    },
    {
      "track": "ravenbridge_mansion",
      "t": 2844.5,
      "items_collected": 4,
      "spinouts": 0,
      "skid_time": 45.14
    },
    {
      "track": "stk_enterprise",
      "t": 3158.1,
      "items_collected": 28,
      "spinouts": 2,
      "skid_time": 36.94
    }
  ]
}
JSON
