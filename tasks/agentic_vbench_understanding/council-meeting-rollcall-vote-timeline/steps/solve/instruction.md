# Council Roll-Call Vote Timeline

You are given one video at `/workspace/materials/issaquah_city_council_2021-12-06.mov`:
the full Issaquah City Council regular meeting from December 6, 2021.

Reconstruct the complete timeline of agenda items in this meeting that have roll-call
votes. For each such agenda item, identify its start time and count spoken public
comments that clearly address that item. For each roll-call vote, identify the vote
time, motion type, mover, seconder, final result, each councilmember's vote, absences,
and any mayoral tie-break vote.

Use the meeting video as your evidence. The spoken agenda labels, council discussion,
public-comment section, and roll-call audio are all relevant.

## Closed vocabularies

Agenda item IDs:

- `consent_calendar`
- `AB 8256`
- `AB 8292`
- `AB 8303`

Motion types:

- `approve_consent_calendar`
- `amend_motion`
- `adopt_resolution`
- `adopt_ordinance_and_ratify_mous`
- `approve_motion_as_amended`

Vote results:

- `passed`
- `passed_after_mayoral_tie_break`
- `failed`

Councilmember names:

- `Barbara de Michele`
- `Stacy Goodman`
- `Zach Hall`
- `Victoria Hunt`
- `Tola Marts`
- `Chris Reh`
- `Lindsey Walsh`

Mayor name:

- `Mary Lou Pauly`

## What counts as a spoken item-linked public comment

Count only audience-comment speakers whose spoken comment clearly addresses the agenda
item. Do not count email summaries, staff presentations, council discussion, ceremonial
recognition comments, or general thanks unless the speaker also clearly addresses the
agenda item.

## What to submit

Write `/workspace/output/solution.json` in exactly this shape. Replace every
placeholder with values derived from the video; do not include placeholder text in
your final JSON:

```json
{
  "agenda_items": [
    {
      "agenda_item_id": "<agenda_item_id>",
      "item_start_time": "HH:MM:SS",
      "spoken_item_linked_public_comment_count": 0
    }
  ],
  "vote_events": [
    {
      "agenda_item_id": "<agenda_item_id>",
      "vote_time": "HH:MM:SS",
      "motion_type": "<motion_type>",
      "mover": "<councilmember name>",
      "seconder": "<councilmember name>",
      "result": "<result>",
      "yes": ["<councilmember name>"],
      "no": ["<councilmember name>"],
      "absent": ["<councilmember name>"],
      "tie_breaker": null
    },
    {
      "agenda_item_id": "<agenda_item_id>",
      "vote_time": "HH:MM:SS",
      "motion_type": "<motion_type>",
      "mover": "<councilmember name>",
      "seconder": "<councilmember name>",
      "result": "<result>",
      "yes": ["<councilmember name>"],
      "no": ["<councilmember name>"],
      "absent": ["<councilmember name>"],
      "tie_breaker": {"name": "Mary Lou Pauly", "vote": "yes"}
    }
  ]
}
```

- Include one `agenda_items` entry for each agenda item ID above that has one or more
  roll-call votes.
- Include one `vote_events` entry per roll-call vote, in any order.
- Times are elapsed time from the start of the video in `HH:MM:SS`. Aim to be within
  20 seconds for each timestamp.
- The `yes`, `no`, and `absent` arrays should contain councilmember names only.
- For a mayoral tie-break, keep councilmember votes in `yes` and `no`, and put the
  mayor's vote in `tie_breaker`.

## Rules

- Stay inside this working directory. Do not read, write, or search outside it.
- Do not look anything up online. Solve from the provided meeting video.
- Do not use transcript files, captions downloaded from the internet, official
  minutes, or motion reports. If you create your own notes from the video, keep them
  under `/workspace/work`.
