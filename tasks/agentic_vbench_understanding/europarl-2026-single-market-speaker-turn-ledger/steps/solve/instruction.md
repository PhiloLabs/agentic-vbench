# European Parliament Speaker-Turn Ledger

You are given:

- `/workspace/materials/debate.mp4`: one continuous European Parliament debate with original floor audio;
- `/workspace/materials/roster.json`: the anonymous speaker IDs available for your answer;
- `/workspace/materials/roster/`: one official reference portrait per anonymous speaker ID;
- `/workspace/materials/excerpts.json`: shuffled anonymous English inference
  cards, each stating a source-entailed counterfactual, implication, policy test,
  or premise/outcome tension from one scored intervention.

Reconstruct the complete chronological ledger of substantive speaker turns.

A substantive turn:

- belongs to the person delivering the speech, not the presiding chair;
- lasts at least 30 seconds;
- starts at the floor-audio handover into that speaker's intervention, which can
  precede the first spoken word by a brief pause;
- ends at the floor-audio handover away from that speaker.

The scored official interval may include a few seconds of overlapping chair
speech or room audio at either handover. Report the official intervention window,
not a voice-activity-only crop.

Exclude short chair or presiding-officer interjections. Preserve separate
appearances by the same speaker as separate turns. Include borderline
interventions that span approximately 30 seconds rather than rounding them down.
Use the portraits and visible speaker to identify `speaker_id`; use the floor
audio to locate the intervention boundaries.
Also identify the language spoken on the original floor track. Use one of these
ISO 639-1 codes:

`bg`, `cs`, `da`, `de`, `el`, `en`, `es`, `fi`, `fr`, `hr`, `hu`, `it`, `lt`,
`lv`, `nl`, `pl`, `pt`, `ro`, `sk`, `sl`, `sv`.

The offline command `detect-language <audio.wav> [...]` is available. It accepts
one or more 16 kHz mono WAV excerpts and returns JSON with the top language codes.
The offline command `transcribe-audio [--task transcribe|translate]
<audio.wav> [...]` is also available and returns detected language plus transcript
text. Translation mode produces English text for cross-lingual card matching.
Each input excerpt must be at most 180 seconds; split long audio before invoking
the command so one broad transcription cannot consume the task runtime. Run only
one `transcribe-audio` process at a time; pass multiple clips to that one command
to batch them safely within the memory limit.
Treat language detection as a candidate ranking rather than an oracle and
cross-check uncertain or accented speech against the transcript.

Match each intervention's spoken content to exactly one `excerpt_id` from
`excerpts.json`. The cards express inferential consequences rather than quotations
or summaries; they are shuffled and do not reveal speaker identity, order, or
timestamps.

Boundary estimates should be within 3.5 seconds.

Write `/workspace/output/solution.json` in exactly this shape:

```json
{
  "turns": [
    {
      "turn_index": 1,
      "speaker_id": "speaker_001",
      "language_code": "en",
      "excerpt_id": "excerpt_001",
      "start_time_s": 42.0,
      "end_time_s": 105.0
    }
  ]
}
```

Requirements:

- `turn_index`: consecutive one-based chronological index.
- `speaker_id`: one ID present in `roster.json`.
- `language_code`: one code from the supplied closed vocabulary.
- `excerpt_id`: one ID present in `excerpts.json`.
- `start_time_s`, `end_time_s`: seconds from the beginning of `debate.mp4`.
- Turns must be ordered chronologically and each end must be after its start.

Use only the supplied materials. Do not use internet lookup, public schedules,
external speaker lists, prior knowledge of the sitting, or memory of public figures.
