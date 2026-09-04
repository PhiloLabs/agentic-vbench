#!/bin/bash
# Oracle: hero (tux) per-race counts + skid_time (VIDEO seconds), each tagged with its video time t.
set -euo pipefail
# Write where the verifier reads it (tests/test.sh: judge.py --solution /workspace/output/solution.json)
# and where the agent prompt tells the agent to write. SOLUTION_PATH overrides only for local tests.
OUT="${SOLUTION_PATH:-/workspace/output/solution.json}"
mkdir -p "$(dirname "$OUT")"
cat > "$OUT" <<'JSON'
{
  "races": [
    {
      "track": "hacienda",
      "t": 119.4,
      "items_collected": 5,
      "spinouts": 5,
      "skid_time": 64.83
    },
    {
      "track": "snowmountain",
      "t": 358.5,
      "items_collected": 14,
      "spinouts": 5,
      "skid_time": 56.65
    },
    {
      "track": "cornfield_crossing",
      "t": 654.8,
      "items_collected": 4,
      "spinouts": 9,
      "skid_time": 45.66
    },
    {
      "track": "lighthouse",
      "t": 931.5,
      "items_collected": 11,
      "spinouts": 1,
      "skid_time": 78.62
    },
    {
      "track": "gran_paradiso_island",
      "t": 1237.0,
      "items_collected": 13,
      "spinouts": 4,
      "skid_time": 145.58
    },
    {
      "track": "sandtrack",
      "t": 1556.0,
      "items_collected": 14,
      "spinouts": 2,
      "skid_time": 15.85
    },
    {
      "track": "olivermath",
      "t": 1734.6,
      "items_collected": 6,
      "spinouts": 4,
      "skid_time": 25.18
    },
    {
      "track": "cocoa_temple",
      "t": 1996.3,
      "items_collected": 13,
      "spinouts": 0,
      "skid_time": 53.91
    },
    {
      "track": "scotland",
      "t": 2327.2,
      "items_collected": 12,
      "spinouts": 3,
      "skid_time": 89.95
    },
    {
      "track": "fortmagma",
      "t": 2591.2,
      "items_collected": 16,
      "spinouts": 4,
      "skid_time": 64.78
    },
    {
      "track": "ravenbridge_mansion",
      "t": 2898.6,
      "items_collected": 7,
      "spinouts": 1,
      "skid_time": 45.88
    },
    {
      "track": "stk_enterprise",
      "t": 3224.8,
      "items_collected": 25,
      "spinouts": 4,
      "skid_time": 31.07
    }
  ]
}
JSON
