#!/bin/bash
# Oracle: SuperTuxKart profile-mode powerup counts for each recorded race.
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
          "items_collected": 17
        },
        {
          "kart": "wilber",
          "items_collected": 19
        },
        {
          "kart": "kiki",
          "items_collected": 8
        },
        {
          "kart": "xue",
          "items_collected": 11
        },
        {
          "kart": "beastie",
          "items_collected": 12
        },
        {
          "kart": "konqi",
          "items_collected": 7
        },
        {
          "kart": "gnu",
          "items_collected": 14
        },
        {
          "kart": "puffy",
          "items_collected": 5
        },
        {
          "kart": "amanda",
          "items_collected": 10
        },
        {
          "kart": "tux",
          "items_collected": 14
        },
        {
          "kart": "nolok",
          "items_collected": 8
        },
        {
          "kart": "pidgin",
          "items_collected": 7
        }
      ]
    },
    {
      "track": "snowmountain",
      "karts": [
        {
          "kart": "emule",
          "items_collected": 13
        },
        {
          "kart": "hexley",
          "items_collected": 8
        },
        {
          "kart": "wilber",
          "items_collected": 12
        },
        {
          "kart": "tux",
          "items_collected": 8
        },
        {
          "kart": "amanda",
          "items_collected": 11
        },
        {
          "kart": "konqi",
          "items_collected": 9
        },
        {
          "kart": "xue",
          "items_collected": 9
        },
        {
          "kart": "pidgin",
          "items_collected": 10
        },
        {
          "kart": "nolok",
          "items_collected": 5
        },
        {
          "kart": "suzanne",
          "items_collected": 8
        },
        {
          "kart": "puffy",
          "items_collected": 8
        },
        {
          "kart": "gnu",
          "items_collected": 7
        }
      ]
    },
    {
      "track": "lighthouse",
      "karts": [
        {
          "kart": "suzanne",
          "items_collected": 12
        },
        {
          "kart": "hexley",
          "items_collected": 8
        },
        {
          "kart": "kiki",
          "items_collected": 7
        },
        {
          "kart": "gavroche",
          "items_collected": 8
        },
        {
          "kart": "tux",
          "items_collected": 10
        },
        {
          "kart": "nolok",
          "items_collected": 8
        },
        {
          "kart": "xue",
          "items_collected": 11
        },
        {
          "kart": "beastie",
          "items_collected": 11
        },
        {
          "kart": "sara_the_wizard",
          "items_collected": 6
        },
        {
          "kart": "sara_the_racer",
          "items_collected": 9
        },
        {
          "kart": "adiumy",
          "items_collected": 12
        },
        {
          "kart": "emule",
          "items_collected": 10
        }
      ]
    },
    {
      "track": "cornfield_crossing",
      "karts": [
        {
          "kart": "tux",
          "items_collected": 10
        },
        {
          "kart": "pidgin",
          "items_collected": 8
        },
        {
          "kart": "gavroche",
          "items_collected": 3
        },
        {
          "kart": "puffy",
          "items_collected": 9
        },
        {
          "kart": "emule",
          "items_collected": 3
        },
        {
          "kart": "gnu",
          "items_collected": 4
        },
        {
          "kart": "konqi",
          "items_collected": 2
        },
        {
          "kart": "xue",
          "items_collected": 5
        },
        {
          "kart": "wilber",
          "items_collected": 7
        },
        {
          "kart": "nolok",
          "items_collected": 5
        },
        {
          "kart": "amanda",
          "items_collected": 4
        },
        {
          "kart": "beastie",
          "items_collected": 5
        }
      ]
    },
    {
      "track": "scotland",
      "karts": [
        {
          "kart": "suzanne",
          "items_collected": 12
        },
        {
          "kart": "konqi",
          "items_collected": 12
        },
        {
          "kart": "gavroche",
          "items_collected": 15
        },
        {
          "kart": "wilber",
          "items_collected": 15
        },
        {
          "kart": "kiki",
          "items_collected": 15
        },
        {
          "kart": "sara_the_wizard",
          "items_collected": 8
        },
        {
          "kart": "emule",
          "items_collected": 4
        },
        {
          "kart": "sara_the_racer",
          "items_collected": 11
        },
        {
          "kart": "beastie",
          "items_collected": 10
        },
        {
          "kart": "hexley",
          "items_collected": 5
        },
        {
          "kart": "adiumy",
          "items_collected": 6
        },
        {
          "kart": "amanda",
          "items_collected": 7
        }
      ]
    },
    {
      "track": "black_forest",
      "karts": [
        {
          "kart": "tux",
          "items_collected": 36
        },
        {
          "kart": "suzanne",
          "items_collected": 23
        },
        {
          "kart": "emule",
          "items_collected": 38
        },
        {
          "kart": "nolok",
          "items_collected": 28
        },
        {
          "kart": "hexley",
          "items_collected": 31
        },
        {
          "kart": "kiki",
          "items_collected": 24
        },
        {
          "kart": "sara_the_racer",
          "items_collected": 21
        },
        {
          "kart": "puffy",
          "items_collected": 20
        },
        {
          "kart": "pidgin",
          "items_collected": 23
        },
        {
          "kart": "xue",
          "items_collected": 19
        },
        {
          "kart": "adiumy",
          "items_collected": 21
        },
        {
          "kart": "gnu",
          "items_collected": 35
        }
      ]
    }
  ]
}
JSON
