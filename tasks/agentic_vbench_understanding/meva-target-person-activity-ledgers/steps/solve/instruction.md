# Target-Person Activity Ledger Reconstruction

You are given:

- `/workspace/materials/meva_activity_montage.mp4`: one silent surveillance montage.
- `/workspace/materials/roster.json`: ten anonymous target references.
- `/workspace/materials/roster/reference_001.jpg` through
  `/workspace/materials/roster/reference_010.jpg`: one image per target.

Reconstruct every visible occurrence of the allowed activities performed by each
pictured target. The references identify video-local targets only; do not infer
that people from different scenes or cameras are the same physical person.

## Allowed activity types

- `person_picks_up_object`: the target lifts an object from a supporting surface
  or the ground.
- `person_carries_heavy_object`: the target visibly transports a bulky or heavy
  object.
- `person_puts_down_object`: the target places a carried object onto a supporting
  surface or the ground.
- `person_opens_vehicle_door`: the target opens a vehicle door.
- `person_enters_vehicle`: the target moves from outside to inside a vehicle.
- `person_closes_vehicle_door`: the target closes a vehicle door.

Report overlapping activities separately. Use seconds from the beginning of the
montage. A temporal match allows up to 3.0 seconds of midpoint error, but start
and end times should describe the visible activity interval as accurately as
possible.

## Output

Write `/workspace/output/solution.json`:

```json
{
  "ledgers": [
    {
      "reference_id": "reference_001",
      "events": [
        {
          "activity_type": "person_picks_up_object",
          "start_time_s": 12.3,
          "end_time_s": 13.1
        }
      ]
    }
  ]
}
```

Requirements:

- Use only `reference_001` through `reference_010`.
- Include each target once. Use an empty `events` list when no qualifying event
  is found.
- List each target's events chronologically.
- Do not duplicate an occurrence.
- Inspect the complete montage.
- Do not use online lookup or external knowledge.
