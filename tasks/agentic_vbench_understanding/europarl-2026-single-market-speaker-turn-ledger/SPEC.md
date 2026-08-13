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
  video: "Anonymous identity is recoverable by matching the visible floor speaker to a 742-person official portrait roster containing 79 speakers and 663 non-speaking distractors."
  audio: "Original floor audio identifies the spoken language, floor handover boundaries, and which shuffled English inference card is entailed by each turn."

question: "Reconstruct every substantive non-chair speaker turn of at least 30 seconds as anonymous speaker identity, original floor-language code, shuffled semantic-card ID, start time, and end time."
output_schema: "JSON {\"turns\":[{turn_index:int, speaker_id:\"speaker_NNN\", language_code:bg|cs|da|de|el|en|es|fi|fr|hr|hu|it|lt|lv|nl|pl|pt|ro|sk|sl|sv, excerpt_id:\"excerpt_NNN\", start_time_s:number, end_time_s:number}]}; chronological, one-based, seconds from video start."

evidence:
  - "t=13-116s, video+audio, first speaker identity, Portuguese floor language, and handover boundaries"
  - "t=3844-3934s, video+audio, a later identity/language transition after the presiding officer changes"
  - "t=7375-7649s, video+audio, final French Commission intervention near the end of the 127-minute source"

ground_truth:
  source: "European Parliament official as-run speaker-list PDF, independently cross-checked record-by-record against the official debate-details HTML"
  tier: machine-truth
  auxiliary_materials: "Public semantic-card wording is model-authored and independently checked against complete official transcripts; it is supplied input material, not the source of the hidden turn labels."
  verification: "calibration/source_provenance.json pins the official sources and hashes. calibration/build_ground_truth.py cross-checks the PDF and HTML records and reproduces gt.json with fixed roster IDs. The exact oracle scores 1.0."

scorer:
  metric: "Monotonic one-to-one event F1; a true positive requires exact speaker_id, exact language_code, exact excerpt_id, and both boundaries within 3.5 seconds."
  oracle_reward: 1.0
  null_reward: 0.0

difficulty:
  strong_agent_reward: 0.034884
  strong_agent_reward_range: "0.023256-0.034884 across accepted Codex and Claude runs"
  tool_call_turns: 184
  agent_model: "Codex CLI 0.147.0 with GPT-5.6 Sol xhigh; VS Code Claude Agent SDK with Claude Opus 4.8 high."
  decomposition: "Binding difficulty is joining 742-way face identity with accurate turn localization: Opus resolves language/card on all 47 boundary-aligned turns but identity on 10; scripted CV resolves identity on 40/41 aligned turns but cards on 6. Combined-actor headroom is 0.4875."

anti_shortcut:
  single_frame: 0.0
  video_only: 0.0
  audio_only: 0.0
  no_media: 0.0
  frame_dump_no_tools: 0.0

input:
  url: "https://huggingface.co/datasets/Jordan8717/agentic-vbench-europarl/resolve/52c28b43c496e842f12cb2b31e08bd14208b87d8/debate.mp4"
  sha256: "fef8b986d03d35d2d61b2ed8104f130dbc125f95cfee8704cee121cc5a2f4e8e"
  auxiliary_url: "https://huggingface.co/datasets/Jordan8717/agentic-vbench-europarl/resolve/adc020288555054866734b29e431795a9ad6b32a/roster.tar.gz"
  auxiliary_sha256: "f8ad7ab83278a2112c2ceab8e13accd373005ef53ef5388588727baa99eef0ea"
  length_min: 127.7
  resolution: 1080
```

Input credit: **© European Union, 2026 — Source: European Parliament**. The
artifact repository links the complete source and current Parliament legal and
Audiovisual Services reuse conditions.

## Prompt-writing checks

- One task: reconstruct the substantive speaker-turn ledger.
- Every scored field, language vocabulary, handover boundary, and the 30-second
  substantive-turn rule are defined.
- The exact output path and JSON shape are stated.
- The agent is forbidden from public lookup, external schedules, and identity memory.
- The instruction does not expose the machine-truth source or F1 calculation.
