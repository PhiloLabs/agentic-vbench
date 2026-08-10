# Reconstruct The ATC Clearance-To-Compliance Ledger

You are given one continuous FlightGear cockpit recording at
`/workspace/materials/flight.mp4`. Spoken air-traffic-control clearances are on
the audio track. The visible analog instruments show how the aircraft responds.

Reconstruct every clearance in chronological order and relate it to the
aircraft's subsequent visible behavior.

The recording contains five independent 12-minute flight legs joined by visible
hard cuts at 720, 1440, 2160, and 2880 seconds. Aircraft state and open
clearances reset at each cut. Supersession and stable-hold windows never cross a
leg boundary. An unfinished clearance at the end of its leg is `incomplete`
unless it is otherwise `violated`.

An offline speech-to-text tool is installed:

```bash
transcribe /workspace/materials/flight.mp4
transcribe /workspace/materials/flight.mp4 --start 600 --end 900
```

It prints timestamped speech segments but no aircraft-state information.
`ffmpeg` and `ffprobe` are available for extracting audio, clips, and frames.

## Instrument layout

The standard six-pack is visible on the left side of the panel:

- airspeed indicator: upper-left round gauge;
- altimeter: upper-right round gauge;
- heading indicator: lower-center round compass card;
- vertical-speed indicator: lower-right round gauge.

The recording contains no selected-heading, selected-altitude, or selected-speed
display. Command targets come from the spoken audio; outcomes come from the
visible instruments.

## Clearance fields

For each clearance report exactly:

- `clearance_index`: one-based chronological index.
- `issued_time_s`: when the controller begins speaking the clearance, in seconds
  from the start of the video.
- `command_type`: one value from the closed vocabulary below.
- `target_value`: the spoken numeric target.
- `target_unit`: `feet`, `degrees`, or `knots`.
- `issue_altitude_ft`, `issue_heading_deg`, `issue_airspeed_kt`: the complete
  three-instrument state at issue time.
- `maximum_commanded_progress`: the greatest nonnegative movement from
  the issue-time value in the commanded direction before the next
  same-dimension clearance or leg end, in `target_unit`.
- `execution_altitude_ft`, `execution_heading_deg`, `execution_airspeed_kt`:
  the complete instrument state at `execution_start_time_s`, or all `null` when
  execution is `null`.
- `completion_altitude_ft`, `completion_heading_deg`,
  `completion_airspeed_kt`: the complete instrument state at
  `completion_time_s`, or all `null` when completion is `null`.
- `ending_altitude_ft`, `ending_heading_deg`, `ending_airspeed_kt`: the complete
  three-instrument state immediately before the next same-dimension clearance
  or leg end.
- `execution_start_time_s`: the first sustained correct-direction response, or
  `null`.
- `completion_time_s`: the first stable completion time, or `null`.
- `status`: one value from the closed vocabulary below.
- `superseded_by_index`: the later same-dimension clearance that replaced this
  one before completion, or `null`.
- `overshoot_bucket`: `none`, `small`, `large`, or `not_applicable`.

Report times to the nearest 0.1 second. Issue times are evaluated within 2
seconds; execution and completion times within 4 seconds.

Heading targets use normalized values from 0 through 359 degrees. Target,
progress, and every state snapshot are evaluated within 25 feet, 2 degrees, or
2 knots according to their unit. Heading progress uses circular distance in the
spoken turn direction.

## Closed vocabularies

`command_type`:

```text
climb
descend
turn_left_heading
turn_right_heading
accelerate
decelerate
```

Spoken speed clearances use “maintain N knots.” Classify them as `accelerate`
when the pre-clearance airspeed is below N and `decelerate` when it is above N.

`status`:

```text
complied
complied_late
superseded
violated
incomplete
```

## Event definitions

Each clearance belongs to one dimension: altitude, heading, or airspeed. A later
clearance supersedes only an unfinished clearance on the same dimension.

`execution_start_time_s` is the first point after issue where the correct trend
is sustained for at least 2 seconds:

- heading: at least 0.5 degrees/second in the commanded turn direction;
- altitude: at least 100 feet/minute in the commanded direction;
- airspeed: at least 0.5 knots/second in the required direction.

`completion_time_s` is the first point after execution from which the indicated
value remains within tolerance until the next same-dimension clearance or the
end of the current flight leg. At least 3 seconds of remaining evidence is required:

- heading: within 8 degrees of target;
- altitude: within 100 feet of target;
- airspeed: within 3 knots of target.

Apply status precedence in this order:

1. `complied_late` or `complied` if stable completion occurs. It is
   `complied_late` when correct execution begins more than 12 seconds after
   issue; otherwise it is `complied`.
2. `superseded` if no stable completion occurs before a later same-dimension
   clearance.
3. `violated` if no supersession occurs and a wrong-direction trend meeting the
   execution threshold is sustained for at least 2 seconds.
4. `incomplete` otherwise, including when the current flight leg ends.

Overshoot is the maximum excursion beyond the target in the commanded direction
before the next same-dimension clearance or leg end:

- heading: `small` when over 8 and at most 15 degrees; `large` when over 15;
- altitude: `small` when over 100 and at most 250 feet; `large` when over 250;
- airspeed: `small` when over 3 and at most 10 knots; `large` when over 10.

Use `none` when the target is not crossed beyond its tolerance.
`not_applicable` is reserved for schema compatibility and is not expected for
the directional clearances in this recording.

## Output

Write `/workspace/output/solution.json` with exactly this shape:

```json
{
  "clearances": [
    {
      "clearance_index": 1,
      "issued_time_s": 42.0,
      "command_type": "turn_left_heading",
      "target_value": 125,
      "target_unit": "degrees",
      "issue_altitude_ft": 4200,
      "issue_heading_deg": 180,
      "issue_airspeed_kt": 105,
      "maximum_commanded_progress": 55,
      "execution_altitude_ft": 4200,
      "execution_heading_deg": 178,
      "execution_airspeed_kt": 105,
      "completion_altitude_ft": 4200,
      "completion_heading_deg": 125,
      "completion_airspeed_kt": 105,
      "ending_altitude_ft": 4200,
      "ending_heading_deg": 125,
      "ending_airspeed_kt": 105,
      "execution_start_time_s": 45.2,
      "completion_time_s": 57.8,
      "status": "complied",
      "superseded_by_index": null,
      "overshoot_bucket": "none"
    }
  ]
}
```

The example only demonstrates the schema. Its values are not an answer.

Use only the supplied files. Do not use online lookup or prior knowledge.
