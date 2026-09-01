---
title: OpenTTGames Rally Event-Chain Reconstruction Spec
summary: Spec Card for full-match table-tennis rally event-chain reconstruction.
read_when: Reviewing or calibrating this task.
---

# Task Spec Card

```yaml
task: agentic_vbench_understanding/openttgames-rally-event-chain

cognitive_level: understanding

modalities_required:
  video: >
    Rally discovery, racket-contact timing, player identity,
    forehand/backhand classification, stroke-technique recognition,
    and terminal-outcome classification require temporal visual evidence.
    Only contacts visible in frame are scored; the camera framing is narrower
    than the playing area, so observability is itself part of the task.
  audio: not used

question: >
  Reconstruct the ordered stroke chain and terminal outcome for every
  live-play rally whose serve contact is visible in a full
  23-minute-55-second table-tennis match.

output_schema: >
  Rally-grouped JSON containing serve timestamp in seconds, an ordered
  timestamped stroke sequence with player, hand, and stroke technique,
  and a timestamped terminal rally outcome. Serve timestamps are matched
  within 1.0 s, stroke timestamps within 0.35 s, and ending timestamps
  within 1.0 s.

evidence:
  - t=7.28s, video, early-match rally requiring serve and ordered stroke-chain reconstruction
  - t=1346.79s, video, late-match rally requiring the same reconstruction near the end of the full video
  - t=102.71s, video, rally 8 terminates on a net-stop that must be distinguished
    from the separate point played later in the same annotation window

ground_truth:
  source: >
    Extended OpenTTGames game_2 frame-level structured annotations from
    moamal01/table_tennis_data commit
    36471a76b969a0340df59258a813bf8214e68e7c,
    data/raw/game_data/train/game_2.json,
    annotation SHA256
    7466f1f8c46316406ae224a17491354eac89f9cc2de858633b6f893573db4fe7.
    Six source-terminal gaps and one two-point serve window are handled as
    explicitly documented bounded video-audit exceptions.
  tier: >
    machine truth from published structured annotations, with bounded
    video-audited terminal exceptions
  verification: >
    Serve events define 92 rally windows. Ordinary exact "net" events are
    treated as non-terminal net crossings, while supported player-prefixed
    ending labels define terminal outcomes. Adjacent identical terminal labels
    within 2 frames are deduplicated. Six live-play windows
    (rally IDs 13, 16, 18, 24, 55, and 73) contain no source terminal
    annotation; only their missing terminal outcomes were completed by
    bounded frame-level inspection of the official video. Serve window 8 spans
    two points - the scoreboard moves 4:3 to 4:4 inside the gap - so it is
    truncated at frame 12325 (102.708 s, the frame at which the net arrests the
    ball's forward motion) with terminal left_net, and the second point is
    excluded in full (12 strokes) because its serve contact frame is not
    resolvable in the source video. Cross-referencing strokes against the
    source's own net/bounce events surfaced 26 unannotated opponent contacts;
    23 were confirmed off-frame and 3 were examined at 1/120 s and found to
    show no labellable contact, so no stroke was added to the benchmark. No
    serve window is silently excluded. Deterministic regeneration produces 92
    benchmark rallies containing 387 source-derived strokes, and the generated
    solution and verifier references are byte-for-byte identical.

scorer:
  metric: >
    Rally discovery uses F1 over serve timestamps matched within 1.0 s.
    Within matched rallies, strokes are matched in order within 0.35 s.
    Stroke semantic credit is awarded only when the complete
    (player, hand, stroke) tuple matches for a timing-aligned stroke.
    Rally-ending credit is awarded only when both the exact ending label
    and ending timestamp within 1.0 s match. The final reward is the
    product of rally-discovery F1, joint rally-ending accuracy,
    stroke-timing F1, and joint stroke-semantic F1.
  oracle_reward: 1.0
  null_reward: 0.0

difficulty:
  # Measured on the reported Claude Code row; the other two harnesses are in
  # calibration/scores.md with the same fields. All three clear both gates.
  strong_agent_reward: 0.041168
  tool_call_turns: 123
  agent_model: Claude Code CLI 2.1.251 / claude-opus-4-8
  # The turn count is the sum of two execution segments of one Claude Code session
  # (86 + 37), separated by a subscription-window interruption and resumed with
  # `claude --continue`. Both segments carry session_id 40ddfba8 and both transcripts
  # are committed. Segment 2 alone would not clear >50. See calibration/scores.md.

anti_shortcut:
  # Complete. Family gate is <= 0.15 and all four clear it, but they are not
  # interchangeable. single_frame and plain no_media are abstention controls; the
  # forced no_media and literal frame_dump_no_tools runs are the non-abstaining
  # evidence. Read the ablations section of calibration/scores.md before comparing.
  single_frame: 0.000000
  # Codex, 4 tool calls. The agent declined to write a solution rather than guess
  # from one still, so this bounds completability, not guessability.
  video_only: not applicable; audio is not a required modality
  audio_only: not applicable; audio is not a required modality
  no_media: 0.000000
  # Two runs are retained. Plain no_media (Codex, 3 calls) is a refusal. The
  # forced-answer variant is the one that bounds recall: told to guess anyway, the
  # agent submitted 96 rallies and 467 strokes spanning 63.4-1388.5 s and matched
  # 19 of 92 rallies and 54 of 387 strokes. Guessing a match-shaped answer is easy;
  # landing serve contacts within 1.0 s and strokes within 0.35 s is not.
  frame_dump_no_tools: 0.000000
  # The literal condition, Claude Code 2.1.251, tool_use count 0. All 1435 frames of
  # the 1 fps sample -- none omitted -- pre-arranged into 30 7x7 contact sheets at
  # 1568x882 and given to the model as image inputs on a single request with every
  # tool disallowed. No shell, no file access, no inspection of any kind. It
  # submitted 43 rallies and matched 3; strokes 5 of 387. On legibility: players,
  # stances, table and net read clearly at 224x126 per tile, but the ball itself is a
  # few pixels and independent inspection could not reliably identify it, so the
  # probe's self-report is not treated as settled. What the run shows instead is that
  # the presentation was usable enough to work from: 73% of its 158 submitted stroke
  # times are non-integer, so it interpolated between sampled instants rather than
  # echoing them, and still matched only 3 rallies and 5 strokes. Sheet digests in
  # calibration/ablations/ablation_frame-dump-notools_sheets.sha256.
  #
  # Disclosure: the two diagnostics that require predicting without observing need an
  # ablation-only override, because rule 4 ("work from the video") otherwise makes the
  # agent abstain, which it did on the first attempts. The mechanism differs between
  # them. Forced no_media appends the override to the CONTAINER copy of the rules and
  # records both digests in its metadata (repository 779eec27..., container
  # fe217b24...). frame_dump_no_tools edits no rules file: it is a single multimodal
  # request issued from /tmp, which has no CLAUDE.md, so the shared rules file is
  # never loaded, and the override exists only in the prompt text. The repository
  # rules file is unmodified in both cases and the frozen task contract is untouched.


input:
  url: https://lab.osai.ai/datasets/openttgames/data/game_2.mp4
  sha256: 330ac07730bae6d899dbbbd00ad43500c583e6af6ea6dd261565bc77811eba66
  length_min: 23.9167
  resolution: 1080
```

## Dataset and provenance summary

- Official video size: 10,833,064,677 bytes
- Video frame rate: 120 fps
- Video frame count: 172,200
- Source annotation events: 1,575
- Serve-defined rally windows: 92
- Published stroke annotations: 399
- Benchmark rallies: 92
- Benchmark strokes: 387
- Silently excluded serve windows: 0
- Bounded source-terminal exceptions: 6
- Exception rally IDs: 13, 16, 18, 24, 55, 73
- Video-gap truncations: 1 (rally 8)
- Strokes excluded by that truncation: 12
- Strokes added by manual audit: 0

The six terminal exceptions change only otherwise-missing terminal outcomes.
The rally 8 truncation removes a second point whose serve contact frame is not
resolvable in the source video. No stroke was added by hand; every benchmark
stroke remains source-derived. See `calibration/source-exception-audit.md` for
the scoped video audit and `calibration/generation_audit.json` for
deterministic generation metadata.

## Observability boundary

The fixed camera framing is narrower than the playing area, so a player who
retreats to return a ball can leave the frame. Cross-referencing the source's
own `net` and `bounce` events against its stroke labels surfaces 26 opponent
contacts that physically occurred but carry no annotation; 23 are confirmed
off-frame and 3 were examined frame by frame without yielding a labellable
contact. The benchmark therefore scores only contacts observable in the media,
and `steps/solve/instruction.md` states that rule to the agent: report only
visible contacts, never infer one from the ball's later path, and omit a rally
whose serve contact is not visible. This keeps the reachable ceiling at 1.0 for
an agent that perceives the video correctly.

## Difficulty

Final calibration is complete and reported in `calibration/scores.md`, run on the
current task image. Scored containers use a default-DROP egress allowlist rather
than a blanket internet switch: task and data lookup endpoints -- the dataset host,
GitHub, the raw-content CDN, and search engines -- are unreachable, while the model
transport each harness needs stays open, since that is inference rather than lookup.
`net_guard` re-proves both halves of that before and after every scored run.

The final calibration record belongs in `calibration/scores.md` and must
include one current-image run each for Codex, Claude Code, and Antigravity,
including harness/model versions, reward, tool-call turns, and the raw native
trajectory location.

## Anti-shortcut checks

The required family conditions are listed below. Each has reported evidence in
`calibration/scores.md`.

- single representative frame only;
- forced answer with no media;
- complete selected 1 fps frame set available directly to the model, with no
  task-inspection tools.

The third condition is met literally rather than by substitute. The complete
selected sample -- all 1435 frames at 1 fps, none omitted -- is pre-arranged into 30
contact sheets and presented to the model as multimodal image inputs on a single
request with every tool disallowed. The agent keeps no shell and makes zero
task-inspection tool calls; `tool_use` count in the retained trajectory is 0. This is
the selected 1 fps set, not the 172,200 native frames.

Each degraded-input run must score at or below 0.15. If one exceeds that
threshold, fix the shortcut rather than changing the threshold.