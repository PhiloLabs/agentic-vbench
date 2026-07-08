# Task Spec Card

```yaml
task: agentic_vbench_understanding/council-meeting-rollcall-vote-timeline

cognitive_level: understanding

modalities_required:
  video: "Needed for elapsed-video timing, meeting navigation, and agenda-transition context."
  audio: "Needed to hear spoken public comments, motions, seconds, roll-call votes, and the mayoral tie-break."

question: "Reconstruct the timeline of every agenda item in the meeting that has a roll-call vote, including item start times, item-linked spoken public-comment counts, and every roll-call vote's mover, seconder, result, councilmember votes, absences, and mayoral tie-break."
output_schema: "JSON at /workspace/output/solution.json with agenda_items[{agenda_item_id,item_start_time,spoken_item_linked_public_comment_count}] and vote_events[{agenda_item_id,vote_time,motion_type,mover,seconder,result,yes,no,absent,tie_breaker}], using HH:MM:SS elapsed-video timestamps."

evidence:
  - "t=00:33:24-00:50:16, audio/video, audience comments establish which spoken comments are item-linked to AB 8256."
  - "t=01:13:08, audio/video, consent-calendar roll-call vote and first unanimous result."
  - "t=01:44:17-01:46:17, audio/video, AB 8256 amendment split vote and main motion vote."
  - "t=01:54:17, audio/video, AB 8292 unanimous roll-call vote."
  - "t=02:24:05-02:25:57, audio/video, AB 8303 council tie and mayoral tie-break."
  - "t=02:26:57, audio/video, AB 8303 main motion as amended."

ground_truth:
  source: "Official Issaquah approved minutes and official motion report for the December 6, 2021 regular council meeting, aligned to the Archive.org video by caption/audio timestamp review."
  tier: machine-truth
  verification: "Official minutes and motion report agree on all dispositions; caption/audio review anchors each roll-call window and item start. AB 8292 and AB 8303 item starts were manually corrected to 01:46:37 and 01:55:09."

scorer:
  metric: "Deterministic F1-like credit over six vote events. Each matched event receives component credit for agenda item, motion type, vote time, item start time, mover/seconder, yes/no/absent sets, result/tie-breaker, and public-comment count."
  oracle_reward: 1.0
  null_reward: 0.0

difficulty:
  strong_agent_reward: "to measure"
  tool_call_turns: "to measure"
  agent_model: "to measure with Antigravity, Codex CLI, and Claude Code CLI"

anti_shortcut:
  single_frame: "to measure"
  video_only: "to measure"
  audio_only: "to measure"
  no_media: "to measure"
  frame_dump_no_tools: "to measure"

input:
  url: "https://archive.org/download/ciwa-Issaquah_City_Council_Regular_Meeting_-_December_6_2021/Issaquah_City_Council_Regular_Meeting_-_December_6_2021.HD.mov?download=1"
  sha256: "d7a08e70571efdfa2ffa9e9e2ed2f98064337b86892916943c218af78bb8a6f1"
  length_min: 150.3
  resolution: "720p"
```
