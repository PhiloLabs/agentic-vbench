#!/bin/bash
# Oracle: write the verified council-meeting roll-call vote timeline.
#
# Reference source: Issaquah approved minutes and official motion report for the
# December 6, 2021 regular meeting, with video timestamps aligned manually from
# the meeting recording. The agent never sees this file.
set -euo pipefail

mkdir -p /workspace/output

python3 - <<'PY'
import json
from pathlib import Path

solution = {
  "agenda_items": [
    {
      "agenda_item_id": "consent_calendar",
      "item_start_time": "01:11:06",
      "spoken_item_linked_public_comment_count": 0,
    },
    {
      "agenda_item_id": "AB 8256",
      "item_start_time": "01:13:32",
      "spoken_item_linked_public_comment_count": 5,
    },
    {
      "agenda_item_id": "AB 8292",
      "item_start_time": "01:46:37",
      "spoken_item_linked_public_comment_count": 0,
    },
    {
      "agenda_item_id": "AB 8303",
      "item_start_time": "01:55:09",
      "spoken_item_linked_public_comment_count": 0,
    },
  ],
  "vote_events": [
    {
      "agenda_item_id": "consent_calendar",
      "vote_time": "01:13:08",
      "motion_type": "approve_consent_calendar",
      "mover": "Victoria Hunt",
      "seconder": "Lindsey Walsh",
      "result": "passed",
      "yes": [
        "Lindsey Walsh",
        "Barbara de Michele",
        "Stacy Goodman",
        "Zach Hall",
        "Victoria Hunt",
        "Tola Marts",
      ],
      "no": [],
      "absent": ["Chris Reh"],
      "tie_breaker": None,
    },
    {
      "agenda_item_id": "AB 8256",
      "vote_time": "01:44:17",
      "motion_type": "amend_motion",
      "mover": "Victoria Hunt",
      "seconder": "Zach Hall",
      "result": "passed",
      "yes": [
        "Barbara de Michele",
        "Zach Hall",
        "Victoria Hunt",
        "Tola Marts",
        "Lindsey Walsh",
      ],
      "no": ["Stacy Goodman"],
      "absent": ["Chris Reh"],
      "tie_breaker": None,
    },
    {
      "agenda_item_id": "AB 8256",
      "vote_time": "01:45:50",
      "motion_type": "adopt_resolution",
      "mover": "Victoria Hunt",
      "seconder": "Barbara de Michele",
      "result": "passed",
      "yes": [
        "Stacy Goodman",
        "Zach Hall",
        "Victoria Hunt",
        "Tola Marts",
        "Lindsey Walsh",
        "Barbara de Michele",
      ],
      "no": [],
      "absent": ["Chris Reh"],
      "tie_breaker": None,
    },
    {
      "agenda_item_id": "AB 8292",
      "vote_time": "01:54:17",
      "motion_type": "adopt_ordinance_and_ratify_mous",
      "mover": "Stacy Goodman",
      "seconder": "Lindsey Walsh",
      "result": "passed",
      "yes": [
        "Zach Hall",
        "Victoria Hunt",
        "Tola Marts",
        "Lindsey Walsh",
        "Barbara de Michele",
        "Stacy Goodman",
      ],
      "no": [],
      "absent": ["Chris Reh"],
      "tie_breaker": None,
    },
    {
      "agenda_item_id": "AB 8303",
      "vote_time": "02:24:05",
      "motion_type": "amend_motion",
      "mover": "Stacy Goodman",
      "seconder": "Tola Marts",
      "result": "passed_after_mayoral_tie_break",
      "yes": ["Stacy Goodman", "Zach Hall", "Tola Marts"],
      "no": ["Barbara de Michele", "Victoria Hunt", "Lindsey Walsh"],
      "absent": ["Chris Reh"],
      "tie_breaker": {"name": "Mary Lou Pauly", "vote": "yes"},
    },
    {
      "agenda_item_id": "AB 8303",
      "vote_time": "02:26:57",
      "motion_type": "approve_motion_as_amended",
      "mover": "Victoria Hunt",
      "seconder": "Lindsey Walsh",
      "result": "passed",
      "yes": [
        "Tola Marts",
        "Lindsey Walsh",
        "Barbara de Michele",
        "Stacy Goodman",
        "Zach Hall",
        "Victoria Hunt",
      ],
      "no": [],
      "absent": ["Chris Reh"],
      "tie_breaker": None,
    },
  ],
}

Path("/workspace/output/solution.json").write_text(json.dumps(solution, indent=2))
PY

echo "oracle: wrote /workspace/output/solution.json (4 agenda items, 6 vote events)"
