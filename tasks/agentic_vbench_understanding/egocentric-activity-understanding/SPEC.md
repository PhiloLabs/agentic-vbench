---
title: Task Spec Card
summary: Verifiable claims for the GTEA Gaze+ egocentric action-ledger task.
read_when: Reviewing the task's media, scorer, ground truth, or calibration evidence.
---

# Task Spec Card

```yaml
task: agentic_vbench_understanding/egocentric-activity-understanding

# 1. What kind of thinking does this task need?
cognitive_level: understanding
# Spotting that a hand is moving is perception. The scored fields are which object is
# being manipulated (the containers are visually near-identical cartons and boxes, told
# apart only by what was taken out of them earlier), which verb applies (take vs put and
# open vs close are the same motion run in opposite directions, separable only by the
# object's state before and after), and where the manipulation starts and stops to
# within a second.

# 2. Which modalities are REQUIRED?
modalities_required:
  video: "Every scored field lives in the pixels. Verb polarity and object identity both
          depend on frames outside the action's own window, so the answer needs the
          video as a sequence, not as isolated frames."
  audio: "not used - the published file carries no audio track."

# 3. The exact question and output schema.
question: "For every object-manipulation action the camera wearer performs in a
           17.8-minute egocentric cooking video, report (verb, nouns, start_frame,
           end_frame)."
output_schema: >
  {"actions": [{"verb": <one of 15 vocabulary verbs>,
                "nouns": [<one or more of 36 vocabulary nouns, no repeats>],
                "start_frame": <int, 0-25691>,
                "end_frame": <int, > start_frame>}, ...]}
  Ordered by non-decreasing start_frame; frame 0 is the first frame, 24 fps.
  Scored with a +/-12-frame (0.5 s) tolerance on BOTH boundaries; see the scorer.

# 4. Evidence chain: far-apart moments the answer depends on.
evidence:
  - "frames 1042-1307: the burner is turned on, then oil is poured from its container
     into the skillet. Both the `oil` noun and the `pour` verb are only readable by
     watching the container tilt over the pan across ~80 frames."
  - "frames 2580-3941, ~57 s later: egg, milk and salt containers are opened, used and
     closed. Deciding `open` vs `close` on each requires the container's state in the
     frames before and after, and telling `egg_container` from `milk_container` from
     `salt_container` requires having seen what came out of each."
  - "frames 21659-22280, ~13 minutes later still: bacon in the skillet is worked in
     alternating `move around` and `flip` segments that abut frame-to-frame
     (21659-21760, 21759-21856, 21856-21959, 21964-21993, ...). Cutting that continuous
     stirring motion at the right frames means watching the spatula's action across the
     whole stretch; no single frame says where one segment ends and the next begins."
  - "172 such actions spread across the whole video; the answer is the full ordered
     ledger, so no single lookup and no single moment suffices."

# 5. Ground truth: value, source, tier, verification.
ground_truth:
  source: "Georgia Tech Egocentric Activity Datasets, GTEA Gaze+, published action
           annotation for subject Ahmad, `American` breakfast session
           (steps/solve/tests/Ahmad_American.txt, shipped verbatim with its original
           steps/solve/tests/labels_readme.txt)."
  tier: human-verified
  verification: "calibration/build_ground_truth.py parses the published label file
                 mechanically (172 lines -> verb / noun set / frame span), asserts every
                 span lies inside the video's 25692 frames, folds the published
                 `eggs` noun into `egg` (NOUN_ALIASES), derives the agent-facing closed
                 vocabulary from the same file (the judge re-derives it from the answer
                 key, so there is only one vocabulary.json), and asserts verifier(oracle) == 1.0.
                 gt.json sha256 9882ca7102abae525d8aebadca4248fd2ef3ad65cb215609a2db054376fd8e7b."

# 6. Scorer: deterministic code only.
scorer:
  metric: "Order-preserving 4-field F1 (steps/solve/tests/judge.py, pure stdlib). A
           predicted action is a true positive only if the verb matches, the noun SET
           matches, and both frame boundaries are within 12 frames of the annotation,
           under a one-to-one order-preserving (LCS) alignment. official_score = F1.
           `verb_and_boundary_matches` and `boundary_only_matches` are reported as
           diagnostics and never enter the reward."
  oracle_reward: 1.0        # measured
  null_reward: 0.0          # measured (empty submission, and malformed submission)

# 7. Difficulty: measured with real strong-agent runs.
difficulty:
  strong_agent_reward: "PENDING - not yet run. See calibration/scores.md."
  tool_call_turns: "PENDING - not yet run."
  agent_model: "PENDING - Antigravity, Codex CLI, and Claude Code CLI runs still owed."

# 8. Anti-shortcut ablations. Target: each <= 0.15.
anti_shortcut:
  single_frame: "PENDING - not yet run."
  video_only: "n/a (the source has no audio track, so video-only is the full task)"
  audio_only: "n/a (no audio)"
  no_media: "0.012712 (measured, best fixed guess over the prompt + vocabulary with no
             video: the most frequent verb/noun class, evenly spaced at the median
             action length, swept over 100-300 entries). Random guessing over the
             vocabulary averages 0.000291. Both far under 0.15."
  frame_dump_no_tools: "PENDING - not yet run."

# 9. Input media.
input:
  url: "https://www.dropbox.com/scl/fi/0sfkl9r59qchz71183s19/Ahmad_American.avi?rlkey=zlywl5mhpv3ycwgurbitq1fn2&dl=1"
  sha256: "f78b9f2c34bdb74eaf125bbb200fece6fd9d285f50b02905c91157f935a1ee24"
  length_min: 17.84
  resolution: 960
```

## Media notes

The published file is named `Ahmad_American.avi` but is a **Matroska** container
(muxed by Lavf53.4.0) holding one H.264 track: 1280x960, 24.000 fps
(`DefaultDuration` 41666666 ns), **25692 frames**, last frame timestamp 1070458 ms,
no audio track. `environment/Dockerfile` bakes it byte-for-byte under a truthful
`.mkv` name and never re-encodes or remuxes it, so frame `n` in the container the agent
gets is frame `n` in the published annotation. The build asserts width, height, frame
rate, packet count, and the absence of an audio stream, and fails loudly if the media
ever stops matching what the answer key assumes.

## Open items flagged for review

1. **Media hosting.** The family requires "a stable, downloadable source (archive.org
   or YouTube)". The URL pinned above is the dataset's own Dropbox distribution point
   from the Georgia Tech project page — authoritative, but a share link rather than a
   content-addressed archive URL. Decide whether to keep it or re-host the file on the
   `agentic_vbench_understanding` HF dataset (the pattern used by the other egocentric
   tasks). The SHA256 above pins the exact bytes either way.

2. **Calibration.** `difficulty` and three of the four ablation rows are PENDING. Codex
   has a completed measured run; Claude Code has a partial run; two Antigravity attempts
   exited before examining the video and are invalid as strong-agent calibration. The
   task does not enter review until `calibration/scores.md` has valid final runs.

3. **Ground-truth tier.** The GTEA Gaze+ annotation is `human-verified` rather than
   `machine-truth`, and the family prefers the highest tier available. For an
   unscripted kitchen session there is no official structured record, so this is the
   ceiling; the mitigation is that the annotation is published, third-party, and
   shipped verbatim rather than re-derived here.

## Prompt-writing checks

- One task: reconstruct the object-manipulation action ledger.
- Every scored term is defined: what starts and ends an action, that overlapping
  actions are both reported, that noun order is irrelevant, and the +/-12-frame
  tolerance.
- Both closed vocabularies (15 verbs, 35 nouns) are given in full, in the prompt and
  as `/workspace/materials/vocabulary.json`.
- Frame indexing is stated explicitly (frame 0 first, 24 fps) with a worked `ffmpeg`
  frame-exact extraction command.
- The exact output path and JSON shape are stated.
- The agent is forbidden from online lookup and from dataset memory.
- The instruction does not reveal the action count, the annotation source, or the F1
  calculation.
