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
  Issue times use a 2-second tolerance; response/completion times use 4 seconds;
  targets use 25 feet, 2 degrees, or 2 knots.

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
    65-event release passed automated media audits and an independent 19-event
    enlarged-frame observability audit.

scorer:
  metric: 0.9 * exact complete-leg chain accuracy + 0.1 * monotonic clearance-chain F1 over five independent 13-clearance legs.
  oracle_reward: 1.0
  null_reward: 0.0

difficulty:
  strong_agent_reward: 0.0
  strong_agent_reward_range: "0.000000-0.010800 across accepted Codex and Claude runs"
  tool_call_turns: 88
  agent_model: Codex CLI 0.147.0 with GPT-5.6 Sol high; maintainer-approved VS Code Claude Agent SDK with Claude Opus 4.8 high.

anti_shortcut:
  single_frame: 0.0
  video_only: 0.0
  audio_only: 0.0031
  no_media: 0.0
  frame_dump_no_tools: 0.0

input:
  url: https://huggingface.co/datasets/Jordan8717/flightgear-atc-clearance-compliance-ledger/resolve/9f301d7fb4b81ceaa73ae98268679aae75fd03d0/flight.mp4
  sha256: a696502dc07cad2ac6e403027e3003f38c9508e527d6f37df2f6bb3b88eeab51
  length_min: 60.0008
  resolution: 720
```
