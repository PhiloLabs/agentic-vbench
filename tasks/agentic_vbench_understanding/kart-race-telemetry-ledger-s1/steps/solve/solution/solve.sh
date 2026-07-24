#!/bin/bash
# Oracle: SuperTuxKart profile-mode powerup and explosion counts per race.
set -euo pipefail
mkdir -p "$(dirname "${SOLUTION_PATH:-/solution/solution.json}")"
cat > "${SOLUTION_PATH:-/solution/solution.json}" <<'JSON'
{
  "races": [
    {
      "track": "hacienda",
      "karts": [
        {
          "kart": "adiumy",
          "items_collected": 17,
          "times_exploded": 1
        },
        {
          "kart": "wilber",
          "items_collected": 19,
          "times_exploded": 1
        },
        {
          "kart": "kiki",
          "items_collected": 8,
          "times_exploded": 2
        },
        {
          "kart": "xue",
          "items_collected": 11,
          "times_exploded": 0
        },
        {
          "kart": "beastie",
          "items_collected": 12,
          "times_exploded": 1
        },
        {
          "kart": "konqi",
          "items_collected": 7,
          "times_exploded": 0
        },
        {
          "kart": "gnu",
          "items_collected": 14,
          "times_exploded": 4
        },
        {
          "kart": "puffy",
          "items_collected": 5,
          "times_exploded": 1
        },
        {
          "kart": "amanda",
          "items_collected": 10,
          "times_exploded": 2
        },
        {
          "kart": "tux",
          "items_collected": 14,
          "times_exploded": 1
        },
        {
          "kart": "nolok",
          "items_collected": 8,
          "times_exploded": 6
        },
        {
          "kart": "pidgin",
          "items_collected": 7,
          "times_exploded": 2
        }
      ]
    },
    {
      "track": "snowmountain",
      "karts": [
        {
          "kart": "emule",
          "items_collected": 13,
          "times_exploded": 0
        },
        {
          "kart": "hexley",
          "items_collected": 8,
          "times_exploded": 0
        },
        {
          "kart": "wilber",
          "items_collected": 12,
          "times_exploded": 1
        },
        {
          "kart": "tux",
          "items_collected": 8,
          "times_exploded": 2
        },
        {
          "kart": "amanda",
          "items_collected": 11,
          "times_exploded": 1
        },
        {
          "kart": "konqi",
          "items_collected": 9,
          "times_exploded": 2
        },
        {
          "kart": "xue",
          "items_collected": 9,
          "times_exploded": 3
        },
        {
          "kart": "pidgin",
          "items_collected": 10,
          "times_exploded": 5
        },
        {
          "kart": "nolok",
          "items_collected": 5,
          "times_exploded": 1
        },
        {
          "kart": "suzanne",
          "items_collected": 8,
          "times_exploded": 2
        },
        {
          "kart": "puffy",
          "items_collected": 8,
          "times_exploded": 2
        },
        {
          "kart": "gnu",
          "items_collected": 7,
          "times_exploded": 4
        }
      ]
    },
    {
      "track": "lighthouse",
      "karts": [
        {
          "kart": "suzanne",
          "items_collected": 12,
          "times_exploded": 0
        },
        {
          "kart": "hexley",
          "items_collected": 8,
          "times_exploded": 0
        },
        {
          "kart": "kiki",
          "items_collected": 7,
          "times_exploded": 1
        },
        {
          "kart": "gavroche",
          "items_collected": 8,
          "times_exploded": 1
        },
        {
          "kart": "tux",
          "items_collected": 10,
          "times_exploded": 3
        },
        {
          "kart": "nolok",
          "items_collected": 8,
          "times_exploded": 3
        },
        {
          "kart": "xue",
          "items_collected": 11,
          "times_exploded": 5
        },
        {
          "kart": "beastie",
          "items_collected": 11,
          "times_exploded": 2
        },
        {
          "kart": "sara_the_wizard",
          "items_collected": 6,
          "times_exploded": 3
        },
        {
          "kart": "sara_the_racer",
          "items_collected": 9,
          "times_exploded": 2
        },
        {
          "kart": "adiumy",
          "items_collected": 12,
          "times_exploded": 3
        },
        {
          "kart": "emule",
          "items_collected": 10,
          "times_exploded": 4
        }
      ]
    },
    {
      "track": "cornfield_crossing",
      "karts": [
        {
          "kart": "tux",
          "items_collected": 10,
          "times_exploded": 0
        },
        {
          "kart": "pidgin",
          "items_collected": 8,
          "times_exploded": 1
        },
        {
          "kart": "gavroche",
          "items_collected": 3,
          "times_exploded": 2
        },
        {
          "kart": "puffy",
          "items_collected": 9,
          "times_exploded": 2
        },
        {
          "kart": "emule",
          "items_collected": 3,
          "times_exploded": 2
        },
        {
          "kart": "gnu",
          "items_collected": 4,
          "times_exploded": 2
        },
        {
          "kart": "konqi",
          "items_collected": 2,
          "times_exploded": 4
        },
        {
          "kart": "xue",
          "items_collected": 5,
          "times_exploded": 4
        },
        {
          "kart": "wilber",
          "items_collected": 7,
          "times_exploded": 4
        },
        {
          "kart": "nolok",
          "items_collected": 5,
          "times_exploded": 6
        },
        {
          "kart": "amanda",
          "items_collected": 4,
          "times_exploded": 5
        },
        {
          "kart": "beastie",
          "items_collected": 5,
          "times_exploded": 5
        }
      ]
    },
    {
      "track": "scotland",
      "karts": [
        {
          "kart": "suzanne",
          "items_collected": 12,
          "times_exploded": 0
        },
        {
          "kart": "konqi",
          "items_collected": 12,
          "times_exploded": 2
        },
        {
          "kart": "gavroche",
          "items_collected": 15,
          "times_exploded": 2
        },
        {
          "kart": "wilber",
          "items_collected": 15,
          "times_exploded": 0
        },
        {
          "kart": "kiki",
          "items_collected": 15,
          "times_exploded": 2
        },
        {
          "kart": "sara_the_wizard",
          "items_collected": 8,
          "times_exploded": 2
        },
        {
          "kart": "emule",
          "items_collected": 4,
          "times_exploded": 3
        },
        {
          "kart": "sara_the_racer",
          "items_collected": 11,
          "times_exploded": 2
        },
        {
          "kart": "beastie",
          "items_collected": 10,
          "times_exploded": 2
        },
        {
          "kart": "hexley",
          "items_collected": 5,
          "times_exploded": 3
        },
        {
          "kart": "adiumy",
          "items_collected": 6,
          "times_exploded": 3
        },
        {
          "kart": "amanda",
          "items_collected": 7,
          "times_exploded": 4
        }
      ]
    },
    {
      "track": "black_forest",
      "karts": [
        {
          "kart": "tux",
          "items_collected": 36,
          "times_exploded": 5
        },
        {
          "kart": "suzanne",
          "items_collected": 23,
          "times_exploded": 3
        },
        {
          "kart": "emule",
          "items_collected": 38,
          "times_exploded": 3
        },
        {
          "kart": "nolok",
          "items_collected": 28,
          "times_exploded": 3
        },
        {
          "kart": "hexley",
          "items_collected": 31,
          "times_exploded": 4
        },
        {
          "kart": "kiki",
          "items_collected": 24,
          "times_exploded": 5
        },
        {
          "kart": "sara_the_racer",
          "items_collected": 21,
          "times_exploded": 6
        },
        {
          "kart": "puffy",
          "items_collected": 20,
          "times_exploded": 5
        },
        {
          "kart": "pidgin",
          "items_collected": 23,
          "times_exploded": 8
        },
        {
          "kart": "xue",
          "items_collected": 19,
          "times_exploded": 7
        },
        {
          "kart": "adiumy",
          "items_collected": 21,
          "times_exploded": 4
        },
        {
          "kart": "gnu",
          "items_collected": 35,
          "times_exploded": 12
        }
      ]
    }
  ]
}
JSON
