# European Parliament Speaker-Turn Ledger

You are given:

- `/workspace/materials/debate.mp4`: one continuous European Parliament debate with original floor audio;
- `/workspace/materials/roster.json`: the anonymous speaker IDs available for your answer;
- `/workspace/materials/roster/`: one official reference portrait per anonymous speaker ID.

Reconstruct the complete chronological ledger of substantive speaker turns.

A substantive turn:

- belongs to the person delivering the speech, not the presiding chair;
- lasts at least 30 seconds;
- starts when that speaker begins the audible floor intervention;
- ends when that speaker's audible floor intervention stops.

Exclude short chair or presiding-officer interjections. Preserve separate appearances
by the same speaker as separate turns. Use the portraits and visible speaker to
identify `speaker_id`; use the floor audio to locate the intervention boundaries.
Boundary estimates should be within 4 seconds.

Write `/workspace/output/solution.json` in exactly this shape:

```json
{
  "turns": [
    {
      "turn_index": 1,
      "speaker_id": "speaker_001",
      "start_time_s": 13.0,
      "end_time_s": 116.0
    }
  ]
}
```

Requirements:

- `turn_index`: consecutive one-based chronological index.
- `speaker_id`: one ID present in `roster.json`.
- `start_time_s`, `end_time_s`: seconds from the beginning of `debate.mp4`.
- Turns must be ordered chronologically and each end must be after its start.

Use only the supplied materials. Do not use internet lookup, public schedules,
external speaker lists, prior knowledge of the sitting, or memory of public figures.
