---
title: FlightGear ATC clearance compliance ledger
summary: Reconstruct spoken clearances and their visible aircraft-response chains across five cockpit flight legs.
read_when: Reviewing the FlightGear agentic omni-understanding task.
---

```yaml
task: agentic_vbench_understanding/flightgear-atc-clearance-compliance-ledger

cognitive_level: reasoning

modalities_required:
  video: Analog cockpit instruments determine response direction, execution onset, stable completion, overshoot, violation, and incompletion.
  audio: Spoken ATC supplies each clearance direction and target; no selected-target display or subtitle reveals it.

question: Reconstruct every spoken ATC clearance and its complete visible execution, completion, status, supersession, and overshoot chain across five independent flight legs.
output_schema: >
  {"clearances": [{"clearance_index": integer, "issued_time_s": seconds,
  "command_type": closed vocabulary, "target_value": number,
  "target_unit": feet|degrees|knots, "issue_altitude_ft": number,
  "issue_heading_deg": number, "issue_airspeed_kt": number,
  "maximum_commanded_progress": number,
  "execution_altitude_ft": number|null, "execution_heading_deg": number|null,
  "execution_airspeed_kt": number|null, "completion_altitude_ft": number|null,
  "completion_heading_deg": number|null, "completion_airspeed_kt": number|null,
  "ending_altitude_ft": number,
  "ending_heading_deg": number, "ending_airspeed_kt": number,
  "execution_start_time_s": seconds|null,
  "completion_time_s": seconds|null, "status": closed vocabulary,
  "superseded_by_index": integer|null,
  "overshoot_bucket": none|small|large|not_applicable}]}.
  Issue times use a 2-second tolerance; execution and completion times are
  graded, earning full credit within 1 second and half within 4; spoken targets
  use 25 feet, 2 degrees, or 2 knots; gauge-read values (state snapshots and
  commanded progress) use 100 feet, 8 degrees, or 3 knots, compared against the
  trajectory interpolated to the timestamp the answer itself reports for that
  snapshot rather than to the true event time.

evidence:
  - t=20.0-29.0s, audio+video, a right-heading clearance is spoken and the heading card visibly turns to and holds 293 degrees.
  - t=225.0-337.6s, audio+video, a climb to 4400 feet visibly crosses the target by more than 250 feet before returning and holding.
  - t=650.0-720.0s, audio+video, an acceleration to 87 knots is followed by visible deceleration to 57 knots and ends violated at the leg cut.
  - t=1045.0-1081.8s, audio+video, a right-heading clearance visibly produces a large overshoot before stable capture.
  - t=3405.0-3427.8s, audio+video, one heading command starts, then a later same-dimension command reverses the turn and supersedes it.
  - t=3550.0-3600.0s, audio+video, the final speed clearance visibly moves in the wrong direction through the end of the fifth leg.

ground_truth:
  source: Executed TTS command log plus FlightGear raw/indicated telemetry and the external controller trace from the exact recorded runs.
  tier: logged
  verification: >
    Five segment validators enforce planned outcome class and overshoot bucket,
    response-after-speech timing, stable holds, visible heading and airspeed
    instrument tracking, and controller/telemetry consistency. The combined
    65-event release passed automated media audits and a full 65-event
    observability audit covering all 235 state snapshots.

scorer:
  metric: >
    Per-clearance graded credit. A predicted clearance matches an expected one
    on command_type plus an issue time inside the 2-second window, aligned
    order-preservingly; it then earns credit group by group out of 20 units:
    target 4, status 4, instrument snapshots 4, timing 4, supersession chain 2
    (which requires a correct overshoot_bucket as well as the resolved link),
    progress 2. Each
    clearance is discounted by the units a transcript-only ledger could have
    earned on that same clearance, so only what the video adds is scored; the
    signed gain is clipped to [-1, 1] so a reading worse than the transcript
    subtracts instead of clipping to zero, and clearances the transcript already
    answers in full are dropped from the denominator. Reward is total credit
    over gradable clearances plus unmatched submissions.
  oracle_reward: 1.0
  null_reward: 0.0

difficulty:
  strong_agent_reward: 0.0938
  strong_agent_reward_range: "0.000000-0.093800 across the three required native runs (Codex 0.0938, Claude 0.0000, Antigravity 0.0000)"
  tool_call_turns: 88
  agent_model: Codex CLI 0.147.0 with GPT-5.6 Sol high; Claude Code 2.1.226 native `claude -p` with Claude Opus 4.8 high; Antigravity CLI 1.1.12 with Gemini 3.6 Flash High.

anti_shortcut:
  single_frame: 0.0
  video_only: 0.0
  audio_only: 0.0
  no_media: 0.0
  frame_dump_no_tools: 0.0

input:
  url: https://huggingface.co/datasets/Jordan8717/flightgear-atc-clearance-compliance-ledger/resolve/9f301d7fb4b81ceaa73ae98268679aae75fd03d0/flight.mp4
  sha256: a696502dc07cad2ac6e403027e3003f38c9508e527d6f37df2f6bb3b88eeab51
  length_min: 60.0008
  resolution: 720
```
