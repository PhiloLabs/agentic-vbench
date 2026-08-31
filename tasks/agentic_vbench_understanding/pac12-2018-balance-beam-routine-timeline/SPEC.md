# 2018 Pac-12 Balance-Beam Routine Timeline

```yaml
task: agentic_vbench_understanding/pac12-2018-balance-beam-routine-timeline

cognitive_level: understanding

modalities_required:
  video: >
    The answer requires distinguishing live foreground beam routines from the
    interleaved apparatuses, replays, warm-ups, and background performances,
    locating every visible mount, final dismount takeoff, and landing boundary,
    and identifying the representing school, gymnast, exact beam score, and
    first frame where the score is shown or becomes derivable from the broadcast.
  audio: not used

question: >
  Find every complete live foreground balance-beam routine in the full
  broadcast and report its mount start, final dismount takeoff, dismount
  landing, school, gymnast name, exact official beam score, and
  score-availability time.

output_schema: >
  {"beam_routines": [{"start_time": "HH:MM:SS.mmm",
  "end_time": "HH:MM:SS.mmm", "dismount_takeoff_time":
  "HH:MM:SS.mmm", "school": "Stanford | Arizona State | Oregon State |
  Arizona", "gymnast_name": "string", "beam_score": "D.DDD",
  "score_time": "HH:MM:SS.mmm"}]}; strict one-to-one F1 uses ±0.25 s
  start, ±0.25 s end, ±0.25 s dismount takeoff, ±1.00 s score time, and
  exact school, gymnast name, and score. Records must be strictly
  chronological. Any malformed or schema-invalid record invalidates the
  whole submission.

evidence:
  - >
    t=00:03:41.721–00:04:58.198 and t=00:08:34.000, video: an early live
    routine establishes the required mount, final dismount takeoff at
    00:04:57.397, landing boundary, beam/apparatus discrimination, Stanford
    school label, and Kaylee Cole identity; the later score graphic establishes
    the 9.725 score and its first readable time.
  - >
    t=02:11:04.356–02:12:16.462, video: a far-later routine requires scanning
    and applying the same boundary rules, including the 02:12:15.761 final
    takeoff, plus the Arizona, Madison Cindric, and inferred 9.850 labels across
    the complete broadcast; the completed beam subtotal first becomes readable
    at t=02:15:12.750.

ground_truth:
  source: original broadcast video only
  tier: human-verified
  verification: >
    A blind second annotator scanned the full broadcast and proposed 24
    candidates. Source-frame adjudication retained 23 complete live foreground
    routines, excluded one mid-routine broadcast entry whose mount was not
    visible, refined every accepted mount, final dismount takeoff, and first
    landing-contact frame, and labeled every row's representing school, gymnast
    name, and official beam score. The reviewer supplied approximate dismount
    takeoffs and direct score-availability times; adjudication resolved every
    takeoff against the 29.97 fps source. The four sixth-gymnast scores and
    evidence times were source-frame adjudicated from completed beam subtotals.
    annotations/status.json records the artifact hashes and completed gate.

scorer:
  metric: >
    Strict one-to-one F1. A true positive must match one unused reference on
    start time within 0.25 s, end time within 0.25 s, dismount takeoff within
    0.25 s, exact school, exact gymnast name, exact three-decimal score string,
    and score time within 1.00 s.
  oracle_reward: 1.0
  null_reward: 0.0

difficulty:
  strong_agent_reward: 0.086957
  tool_call_turns: 55
  agent_model: Codex CLI 0.146.0-alpha.3.1 / gpt-5.6-sol / xhigh

anti_shortcut:
  single_frame: 0.0
  video_only: 0.130435
  audio_only: 0.0
  no_media: 0.0
  frame_dump_no_tools: 0.0

input:
  url: https://www.youtube.com/watch?v=0LtLS9wROrk
  sha256: 7dfc9e139254cc9480948af734988bdebc796c89c6e5d439055a248c251130cb
  length_min: 139.3
  resolution: 1280x720
```

## Source and licensing

The task fetches the public broadcast during environment construction, verifies
the locked source digest, and does not store or rehost the video in git.

A superseded development draft used the CC BY-NC 4.0 FineGym v1.1 annotations as
a candidate index. FineGym data is not distributed by this task and will not be
used by the independent second annotator or to release the final scored key.
The clean-room annotation and adjudication process is documented in
`annotations/README.md`; the historical licensing decision is recorded in
`ANNOTATION_NOTICE.md`.

## Ground-truth result

The human-verified key contains 23 complete live foreground routines with exact
school, gymnast-name, official beam-score, and score-availability-time labels.
Schools are Stanford (6), Arizona State (6), Oregon State (5), and Arizona (6).
Scores are canonical three-decimal strings. The legacy fall-category and
dismount-type labels from the earlier four-field draft remain outside the prompt, schema,
verifier, and reward.

The independent pass and adjudication are complete. Fresh final-contract Codex,
Claude, and Antigravity calibration and all five shortcut ablations are
complete.

The seven-field revision adds `dismount_takeoff_time`, defined as the first
source frame after the final supporting foot or toe loses contact with the beam
and scored within 0.25 s. For connected roundoff or back-handspring dismounts,
the boundary is the final foot rebound into the airborne dismount rather than
the earlier entry into hand support. All 23 takeoffs have been source-frame
adjudicated and the annotation gate is complete.

## Deterministic verifier

The verifier validates the exact seven-field record schema, closed school
vocabulary, non-empty trimmed gymnast names, three-decimal score strings,
timestamp syntax, ordered start/takeoff/end intervals, post-routine score times,
and strictly increasing start times. Any
malformed file, schema-invalid record, extra field, or out-of-order record
receives zero for the whole submission. Otherwise missing and extra valid
records reduce one-to-one F1. School, gymnast name, and score must all match
exactly along with all three action boundaries and score time; diagnostic
counts do not contribute partial reward.

The unit suite includes action-boundary and score-time regressions, an oracle
plus an invalid record, and a reversed oracle. The fresh three-agent and
five-ablation calibration package uses the final scored contract.
