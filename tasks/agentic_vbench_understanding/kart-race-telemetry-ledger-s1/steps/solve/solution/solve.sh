#!/bin/bash
# Oracle: SuperTuxKart profile-mode result table for each recorded race.
set -euo pipefail
mkdir -p "$(dirname "${SOLUTION_PATH:-/solution/solution.json}")"
cat > "${SOLUTION_PATH:-/solution/solution.json}" <<'JSON'
{
  "races": [
    {
      "track": "hacienda",
      "karts": [
        {
          "kart": "beastie",
          "items_collected": 20,
          "nitro_collected": 16
        },
        {
          "kart": "konqi",
          "items_collected": 17,
          "nitro_collected": 12
        },
        {
          "kart": "amanda",
          "items_collected": 18,
          "nitro_collected": 16
        },
        {
          "kart": "adiumy",
          "items_collected": 14,
          "nitro_collected": 16
        },
        {
          "kart": "wilber",
          "items_collected": 17,
          "nitro_collected": 13
        },
        {
          "kart": "gnu",
          "items_collected": 13,
          "nitro_collected": 14
        },
        {
          "kart": "tux",
          "items_collected": 13,
          "nitro_collected": 11
        },
        {
          "kart": "puffy",
          "items_collected": 13,
          "nitro_collected": 14
        },
        {
          "kart": "kiki",
          "items_collected": 17,
          "nitro_collected": 11
        },
        {
          "kart": "nolok",
          "items_collected": 17,
          "nitro_collected": 14
        }
      ]
    },
    {
      "track": "snowmountain",
      "karts": [
        {
          "kart": "gnu",
          "items_collected": 12,
          "nitro_collected": 10
        },
        {
          "kart": "wilber",
          "items_collected": 12,
          "nitro_collected": 13
        },
        {
          "kart": "emule",
          "items_collected": 6,
          "nitro_collected": 9
        },
        {
          "kart": "xue",
          "items_collected": 5,
          "nitro_collected": 9
        },
        {
          "kart": "konqi",
          "items_collected": 4,
          "nitro_collected": 11
        },
        {
          "kart": "puffy",
          "items_collected": 6,
          "nitro_collected": 7
        },
        {
          "kart": "tux",
          "items_collected": 6,
          "nitro_collected": 7
        },
        {
          "kart": "hexley",
          "items_collected": 6,
          "nitro_collected": 3
        },
        {
          "kart": "suzanne",
          "items_collected": 10,
          "nitro_collected": 7
        },
        {
          "kart": "pidgin",
          "items_collected": 12,
          "nitro_collected": 13
        }
      ]
    },
    {
      "track": "lighthouse",
      "karts": [
        {
          "kart": "xue",
          "items_collected": 10,
          "nitro_collected": 15
        },
        {
          "kart": "gavroche",
          "items_collected": 15,
          "nitro_collected": 5
        },
        {
          "kart": "sara_the_racer",
          "items_collected": 11,
          "nitro_collected": 6
        },
        {
          "kart": "hexley",
          "items_collected": 7,
          "nitro_collected": 6
        },
        {
          "kart": "sara_the_wizard",
          "items_collected": 14,
          "nitro_collected": 5
        },
        {
          "kart": "kiki",
          "items_collected": 7,
          "nitro_collected": 6
        },
        {
          "kart": "adiumy",
          "items_collected": 11,
          "nitro_collected": 4
        },
        {
          "kart": "suzanne",
          "items_collected": 9,
          "nitro_collected": 4
        },
        {
          "kart": "emule",
          "items_collected": 9,
          "nitro_collected": 2
        },
        {
          "kart": "nolok",
          "items_collected": 11,
          "nitro_collected": 7
        }
      ]
    },
    {
      "track": "cornfield_crossing",
      "karts": [
        {
          "kart": "puffy",
          "items_collected": 6,
          "nitro_collected": 4
        },
        {
          "kart": "pidgin",
          "items_collected": 5,
          "nitro_collected": 4
        },
        {
          "kart": "tux",
          "items_collected": 5,
          "nitro_collected": 6
        },
        {
          "kart": "amanda",
          "items_collected": 4,
          "nitro_collected": 3
        },
        {
          "kart": "wilber",
          "items_collected": 13,
          "nitro_collected": 2
        },
        {
          "kart": "beastie",
          "items_collected": 9,
          "nitro_collected": 4
        },
        {
          "kart": "konqi",
          "items_collected": 4,
          "nitro_collected": 1
        },
        {
          "kart": "nolok",
          "items_collected": 4,
          "nitro_collected": 4
        },
        {
          "kart": "xue",
          "items_collected": 9,
          "nitro_collected": 4
        },
        {
          "kart": "gnu",
          "items_collected": 6,
          "nitro_collected": 5
        }
      ]
    },
    {
      "track": "scotland",
      "karts": [
        {
          "kart": "gavroche",
          "items_collected": 11,
          "nitro_collected": 15
        },
        {
          "kart": "emule",
          "items_collected": 11,
          "nitro_collected": 15
        },
        {
          "kart": "suzanne",
          "items_collected": 16,
          "nitro_collected": 13
        },
        {
          "kart": "sara_the_wizard",
          "items_collected": 10,
          "nitro_collected": 8
        },
        {
          "kart": "sara_the_racer",
          "items_collected": 13,
          "nitro_collected": 11
        },
        {
          "kart": "hexley",
          "items_collected": 4,
          "nitro_collected": 11
        },
        {
          "kart": "amanda",
          "items_collected": 14,
          "nitro_collected": 11
        },
        {
          "kart": "beastie",
          "items_collected": 11,
          "nitro_collected": 9
        },
        {
          "kart": "kiki",
          "items_collected": 10,
          "nitro_collected": 11
        },
        {
          "kart": "adiumy",
          "items_collected": 11,
          "nitro_collected": 13
        }
      ]
    }
  ]
}
JSON
