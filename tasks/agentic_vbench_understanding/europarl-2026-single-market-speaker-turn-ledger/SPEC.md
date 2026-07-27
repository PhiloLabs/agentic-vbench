---
title: Task Spec Card
summary: Verifiable claims for the European Parliament speaker-turn ledger task.
read_when: Reviewing the task's media, scorer, observability, or calibration evidence.
---

# Task Spec Card

```yaml
task: agentic_vbench_understanding/europarl-2026-single-market-speaker-turn-ledger

cognitive_level: understanding

modalities_required:
  video: "Anonymous identity is recoverable by matching the visible floor speaker to one of 79 supplied official portraits."
  audio: "Original floor audio defines intervention starts and ends; camera cuts routinely lag the audible boundary by up to 15 seconds."

question: "Reconstruct every substantive non-chair speaker turn of at least 30 seconds as anonymous speaker identity, start time, and end time."
output_schema: "JSON {\"turns\":[{turn_index:int, speaker_id:\"speaker_NNN\", start_time_s:number, end_time_s:number}]}; chronological, one-based, seconds from video start."

evidence:
  - "t=13-116s, video+audio, first speaker identity and floor-audio boundaries"
  - "t=3844-3934s, video+audio, a speaker after the presiding officer changes; requires maintaining the global anonymous roster ledger"
  - "t=7375-7649s, video+audio, final Commission intervention near the end of the 127-minute source"

ground_truth:
  source: "European Parliament official as-run speaker-list PDF, independently cross-checked record-by-record against the official debate-details HTML"
  tier: machine-truth
  verification: "Source URLs, retrieval hashes, and counts are in calibration/source_provenance.json; calibration/build_ground_truth.py reproduces gt.json byte-for-byte from the official PDF and HTML. The fixed rule yields 86 turns from 79 speakers. Player absolute time gives a 3,557 s source seek; the exact file starts at 0.0 s and lasts 7,662.0 s. Nine identical-time comparisons against the independently audited pilot have median mean pixel difference 1.16/255. Ten official original-language speech exports spanning turns 1-86 cross-correlate with the floor track at a consistent 22.75 s pre-roll and 37.25 s post-roll (minimum correlation 0.838). The exact oracle scores 1.0."

scorer:
  metric: "Monotonic one-to-one event F1; a true positive requires exact speaker_id and both boundaries within 4 seconds."
  oracle_reward: 1.0
  null_reward: 0.0

difficulty:
  strong_agent_reward: 0.0
  tool_call_turns: 124
  agent_model: "GPT-5.6 Sol, GitHub Copilot CLI 1.0.75, xhigh; Claude Opus 5 and Gemini 3.5 Flash are also calibrated below"

anti_shortcut:
  single_frame: "0.0 — GPT-5.6 Sol identified one anonymous face but could not produce a valid timed ledger"
  video_only: "0.0 — best-effort GPT-5.6 Sol produced 78 video-derived turns over 269 tool calls, but none matched identity plus both four-second boundaries"
  audio_only: "0.0 — best-effort GPT-5.6 Sol produced 83 audio-derived intervals over 94 tool calls, but anonymous portrait identities were unrecoverable"
  no_media: "0.0 — no-tools GPT-5.6 Sol returned the valid empty ledger from prompt and schema alone"
  frame_dump_no_tools: "0.012 — GPT-5.6 Sol received the complete video as 1 fps chronological frame sheets plus roster sheets, with zero tools"

input:
  url: "https://huggingface.co/datasets/Jordan8717/agentic-vbench-europarl/resolve/457f5752fcd2c08b7b47889a8061535b80f1edc7/debate.mp4"
  sha256: "844fb01dd7806105ebdde677d190822f80e46c2d140c7499006b20345870e1b7"
  length_min: 127.7
  resolution: 1080
```

Input credit: **© European Union, 2026 — Source: European Parliament**. The
artifact repository links the complete source and current Parliament legal and
Audiovisual Services reuse conditions.

## Prompt-writing checks

- One task: reconstruct the substantive speaker-turn ledger.
- Every scored field and the 30-second substantive-turn rule are defined.
- The exact output path and JSON shape are stated.
- The agent is forbidden from public lookup, external schedules, and identity memory.
- The instruction does not expose the machine-truth source or F1 calculation.
