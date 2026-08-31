# Balance-Beam Routine Timeline, Dismount Takeoff, Gymnast, and Score

You are given a complete one-frame-per-second visual dump of the full gymnastics broadcast as timestamped contact-sheet bundles attached to this prompt. No video or audio file is available.

Find every complete balance-beam routine shown as the live foreground
performance. For each routine, report its mount start, final dismount takeoff,
dismount landing, the school the gymnast represents, the gymnast's name, and
the official beam score shown or made derivable by the broadcast for that
routine. Also report the first video timestamp at which enough score
information is readable to determine that individual score.

Use only the attached timestamped frame sheets. This is a no-tools shortcut ablation: do not call any tool, shell command, browser, or file operation.

## Submission

Return exactly this JSON structure in your final response; the ablation harness will save it as `/workspace/output/solution.json`:

```json
{
  "beam_routines": [
    {
      "start_time": "HH:MM:SS.mmm",
      "end_time": "HH:MM:SS.mmm",
      "dismount_takeoff_time": "HH:MM:SS.mmm",
      "school": "<allowed school label>",
      "gymnast_name": "<full broadcast name>",
      "beam_score": "D.DDD",
      "score_time": "HH:MM:SS.mmm"
    }
  ]
}
```

Sort entries strictly chronologically by `start_time`. Use exactly seven fields
per entry. Any malformed record, extra field, or out-of-order entry invalidates
the whole submission.

All four timestamps must use zero-padded `HH:MM:SS.mmm` video timestamps
measured from the beginning of the file.

Use exactly one of these school labels:

- `Stanford`
- `Arizona State`
- `Oregon State`
- `Arizona`

Identify the school from the supplied broadcast's visible team, athlete, and
on-screen context. The school must be correct for a routine to match.

Use the gymnast's full name as displayed or announced by the supplied
broadcast. `gymnast_name` must be a non-empty string with no leading or trailing
whitespace and must match the routine's gymnast exactly.

Use the official individual beam score directly shown for that routine, except
for the sixth-gymnast inference described below. Do not substitute a team total
or another apparatus score. Write `beam_score` as a string with exactly three
digits after the decimal point, including trailing zeroes such as `"9.800"` and
`"9.850"`. The score must match exactly for the record to match. The score
graphic may appear after the dismount or during later coverage, so track the
gymnast-routine association across intervening broadcast cuts.

Write `score_time` as a zero-padded `HH:MM:SS.mmm` timestamp. For a directly
shown individual score, use the first frame on which the gymnast's official
score is readable. The score timestamp is scored with a tight ±1.00-second
tolerance.

The sixth beam gymnast for each school does not receive a later individual
score graphic in this broadcast. Infer that gymnast's score from the completed
beam-rotation subtotal shown in the later standings table. A team beam subtotal
is the sum of its best five scores from the six-person beam lineup. Track all
six lineup scores needed for this calculation, including a score belonging to a
performance omitted from the output because its mount is not visible. In this
broadcast, each sixth score replaces the lowest of the first five; use:

`sixth score = completed beam subtotal - sum(first five scores) + lowest(first five scores)`

For an inferred sixth score, `score_time` is the first frame on which that
school's completed beam subtotal is readable in the standings table. Do not
submit the team subtotal itself as `beam_score`.

## Routine boundaries

- Start at the first visible frame of takeoff or intentional weight transfer
  into the mount. Exclude the salute and passive approach. This timestamp is
  scored with a ±0.25-second tolerance.
- Set `dismount_takeoff_time` to the first frame after the gymnast's final
  supporting foot or toe loses contact with the beam for the dismount. For a
  connected roundoff or back-handspring dismount, use the final foot rebound
  that launches the airborne dismount, not the earlier entry into hand support.
  This timestamp must fall between `start_time` and `end_time` and is scored
  with a ±0.25-second tolerance.
- End at the first frame where the gymnast's feet contact the landing mat after
  the final dismount. This timestamp is scored with a ±0.25-second tolerance.
- Count only distinct, live, foreground routines whose mounts and final landings
  are visible and whose performances are sufficiently complete to evaluate.
- Do not count replays, warm-ups, or incomplete background performances as
  separate routines.

## Constraints

- Stay inside `/workspace`.
- Do not use the internet, web search, or outside knowledge. Do not rely on
  memory of this competition; derive every submitted record only from the attached frame sheets.
- Do not include commentary or evidence fields in the JSON.
- You have one non-extendable 90-minute run for all inspection and writing.
  Checkpoints do not pause or extend that deadline, and the task must not be
  resumed after it expires. Submit the best valid solution before the deadline.

## No-tool constraint

Do not call tools or attempt to write files. Return the proposed solution JSON directly in the final response. The harness will materialize valid returned JSON for deterministic scoring.