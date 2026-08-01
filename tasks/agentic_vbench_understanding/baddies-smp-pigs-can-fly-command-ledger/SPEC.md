---
title: Task Spec Card — baddies-smp-pigs-can-fly-command-ledger
summary: Reconstruct every spoken command and its execution chain in a multiplayer co-op building session.
read_when: Reviewing or building this understanding task.
---

# Task Spec Card

```yaml
task: agentic_vbench_understanding/baddies-smp-pigs-can-fly-command-ledger

# 1. Thinking required
cognitive_level: reasoning
# Links each spoken command to the later on-screen action it caused, resolves deictic
# references, attributes speakers/executors across modalities, and tracks unresolved
# commands over minutes. Not perception: no single moment contains the answer.

# 2. Modalities REQUIRED
modalities_required:
  video: Executor identity, execution timing, and outcome are on-screen facts. Voice
         chat never states who acted or whether it worked; deictic objects ("put THAT
         there") resolve only visually.
  audio: The commands themselves — content, speaker voice, addressee — exist only in
         the live voice chat. Video shows actions but not what was asked or by whom.

# 3. Question + schema
question: >
  Reconstruct every actionable spoken command in the session: speaker, target, action,
  object, who visibly executed it, when execution started, the outcome, and the video
  interval showing the execution.
output_schema: >
  {"commands": [{"command_time_s": float, "speaker": <player vocab>, "target":
  <player vocab|group>, "action": <closed vocab>, "object": <closed vocab>,
  "executor": <player vocab|none>, "outcome":
  "completed|partial|corrected|not_done", "execution_start_s": float|null,
  "evidence_start_s": float|null, "evidence_end_s": float|null}]}
  # tolerances: command time 5s, execution start 10s, evidence IoU >= 0.5

# 4. Evidence chain (>= 2 far-apart moments, both modalities)
evidence:
  - audio, command moment: who asks whom for what (often minutes before execution)
  - video, execution moment: who actually does it, when, and whether it succeeds
  - video, later: corrections/reversals that change the outcome label
  # measured example from the source VOD @~01:01: "can you get in here, please? I
  # need that Aisha carrot" -> partner enters and acts on screen shortly after

# 5. Ground truth
ground_truth:
  source: >
    21 deferred requests over the baked 228-min window (first at 872 s, last execution
    at 13223 s). 178 candidates were screened in three passes whose union was used: a
    regex pass over the ASR transcript (76), a full-transcript recall sweep by reading
    agents (35 more, which contributed 9 of the surviving rows — the regex alone missed
    real commands such as "lead the boat, not the pig"), a second-window pass (56), and
    a targeted deferral sweep (11) sampled at BOTH ends of the gap, because earlier
    packets only showed frames out to +120 s while the fulfilment sat 273-1284 s later.
    Candidates were annotated TWICE, independently, by two different vision models
    (Claude Opus 5 and Codex GPT-5.6 Sol at xhigh), each given the same instructions and
    the same frame strip per candidate and free to extract more frames. Disagreements
    were adjudicated from dense frame sampling under
    `media/annotation/ADJUDICATION_RUBRIC.md`; every kept row cites the frames that
    settled it in `steps/solve/tests/ground_truth_provenance.json`.
  tier: model-annotated, adjudicated, reviewed by ONE human (the contributor)
  verification: >
    MEASURED inter-annotator agreement on whether a candidate is an actionable command:
    97.3% raw, Cohen's kappa 0.916 over the first 111 candidates (both yes 21, both no
    87, opus-only 1, codex-only 2). Full-row agreement across the video-grounded fields
    was only 4 of 24 — the two models nearly always agree on the language judgement and
    diverge on what the screen shows, which is where this task's difficulty lives.

    HUMAN PASS: the contributor reviewed the frozen ledger end-to-end on 2026-08-01
    against the per-row frame citations and found no corrections.

    REMAINING GAP: that is ONE human reviewer, and the same person who built the
    annotation pipeline. The family asks for 2+ INDEPENDENT human annotators, so this
    is not yet a clean pass on that requirement — a second reviewer with no stake in
    the pipeline has not looked at it. The per-row frame citations exist precisely so
    that second pass is a check rather than a redo.

    Rows deliberately DROPPED as unanswerable from the media (rubric R2), so the oracle
    is honestly 1.0: #22 (who picked up a dropped lead — no second player visible in any
    sampled frame), #16 and #85 (two different players fly the same coached manoeuvre,
    one inside the scoring window and one just outside, so the executor has two
    frame-supported answers), #20 (retrospective praise for a feat already performed,
    not a directive). One near-duplicate row pair 4 s apart was also merged after it
    produced contradictory outcomes for the same utterance.

# 6. Scorer
scorer:
  metric: >
    Event-level F1, one-to-one bipartite. A TP requires action, object, executor and
    outcome to match (normalized), command time within 5s, execution start within 10s,
    and evidence-window IoU >= 0.5 with the true execution interval. `speaker` and
    `target` are asked for and reported in the diagnostics but NOT scored — see
    "Why speaker/target are unscored" below.
  oracle_reward: 1.0        # PROVEN on synthetic fixtures (tools/test_judge.py)
  null_reward: 0.0          # PROVEN (empty submission)

# 7. Difficulty — MEASURED 2026-08-01 on the shipped 228-min bake. DOES NOT PASS.
difficulty:
  gate: strong agent < 0.10
  strong_agent_reward: 0.1875     # Opus 5 xhigh — FAILS the gate (3 TP over 11 rows)
  second_agent_reward: 0.1379     # Opus 4.8      — FAILS the gate (2 TP over 8 rows)
  third_agent_reward:  0.0741     # Codex GPT-5.6 Sol xhigh — passes (1 TP over 6 rows)
  tool_call_turns: 115 / 51 / 112 # gate is > 50: PASSES for all three
  verdict: >
    The strongest agent solves 3 of 21 rows. Because this metric is event-level F1 with
    predictions and ground truth at comparable size, the reward converges toward the
    agent's solve RATE (~14%) rather than being diluted by ledger size — pushing Opus 5
    under 0.10 at 3 TP and 11 predictions would need N > 49 ground-truth rows. Enlarging
    the ledger is therefore not a route to the gate.

    MEASURED AND REJECTED: raising the deferral floor, on the theory that longer gaps
    are harder. It is not — the agents solve long-gap rows as readily as short ones, so
    the filter removes ground-truth rows and agent true positives at the same rate:
      floor  rows  Opus5          Opus4.8        Codex
       15 s   18   0.2069 (3 TP)  0.0769 (1 TP)  0.0000
       45 s   12   0.0870 (1 TP)  0.1000 (1 TP)  0.0000
       90 s   10   0.0952 (1 TP)  0.1111 (1 TP)  0.0000
      180 s    6   0.1176 (1 TP)  0.1429 (1 TP)  0.0000
    No floor clears the gate for both agents. The deferral gap is not this task's
    difficulty axis; whether the execution is VISUALLY inconspicuous is. That axis was
    then MEASURED rather than left as a suggestion — see below.
  agent_model: Claude Opus 5 (xhigh), Claude Opus 4.8, Codex GPT-5.6 Sol (xhigh)

# 7b. The real difficulty axis, measured (2026-08-01)
#     A controlled test of "visual inconspicuousness", plus what it would cost to build
#     a task on it. Both are reported because the second half is discouraging.
conspicuousness:
  method: >
    For every ground-truth row, the fraction of pixels changing between exec-3 s and
    exec+8 s, minus the same span 45 s earlier in the same scene (a per-row baseline for
    how much this camera moves anyway). Deterministic, no model in the loop.
  controlled_comparison: >
    The 21 rows split into three tiers by what the agents did: SOLVED (4), request
    LOCATED but execution never grounded (4), and never found at all (13). Tier 3 is
    confounded — those may be missed because the request was missed in the transcript.
    Tiers 1 and 2 are not: in both, the agent heard the request, so the only difference
    is whether it could pin the execution. That is a clean 4-vs-4 comparison.
  result:
    frac_changed_minus_baseline: solved +0.289 vs located-only -0.259   # diff +0.548
    mean_abs_diff_minus_baseline: solved +31.19 vs located-only -18.26  # diff +49.45
    exact_permutation_p: 0.043     # one-sided; the FLOOR for n=4 vs 4 is 1/70 = 0.014
    rows_below_0.35_footprint: 6
    of_those_solved_by_any_agent: 0
  honest_limits: >
    n is 4 vs 4 and p 0.043 is close to the best this design can produce, so this is
    suggestive, not settled. The 0.35 threshold was also chosen by looking at which rows
    went unsolved, so quoting it back on the same 21 rows would be circular — it has to
    be validated on rows this measurement never saw.

# 7c. What building that revision would cost — surveyed, not guessed
revision_feasibility:
  source_pool: >
    The channel has 326 videos / 1357 h; 136 are the same server; per-video licence
    checks (licence is per video, not per channel — a sibling session in this same
    series is standard-licence) leave 42 CC-BY sessions / 191 h.
  what_was_run: >
    7 sessions pulled as audio only (~200 MB each instead of ~3 GB), transcribed on
    SLURM (19,638 lines / 30 h, 99-100% coverage), then swept for deferred requests by
    16 subagents across three passes.
  blocking_finding: >
    Yield depends on whether the two players CO-BUILD, and almost none of them do. Of
    10 new half-sessions, 0 are shared projects (7 parallel play, 3 solo); both halves
    of the shipped session are shared projects. A positive control — the identical
    strict sweep re-run on THIS session, whose true ledger of 21 is known — returned 9
    candidates, i.e. the sweep has ~43% recall, so the sweep counts are calibrated
    rather than taken at face value. Per line, this session still yields 3.2x more than
    the others.
  projection: >
    Extrapolating at the measured recall, 7 further sessions plus this one would produce
    roughly 11-13 rows below the footprint threshold. At N=12 a single lucky agent hit
    scores 2/(11+12) = 0.087 and still passes, but two hits give 0.174 and fail. That is
    a one-hit margin, and the hotel-era sessions where this footage's collaboration
    actually happens are almost all standard-licence: 2 of 18 are CC-BY, one of which is
    already swept and is parallel play. The axis is real; the footage to exploit it at
    scale is not obviously there.

# 8. Anti-shortcut ablations — MEASURED 2026-07-30 with Codex GPT-5.6 Sol (xhigh)
#    against the frozen 21-row ground truth. Gate is <= 0.15.
anti_shortcut:
  video_only: 0.0     # audio REMOVED (-an); 4 rows, 0 correct, detection F1 0.00 (92 turns)
  audio_only: 0.0     # audio alone (-vn); 6 rows, 0 correct, detection F1 0.30 (41 turns)
  no_media: 0.0       # prompt + vocab only; submitted nothing (4 turns)
  single_frame: 0.0   # one still at 6843 s; submitted nothing (5 turns)
  frame_dump_no_tools: 0.0   # 20 stills every 684 s, no tools; submitted nothing (3 turns)
  # Every ablation is 0.0000 against a <= 0.15 gate, and the two single-modality runs
  # fail DIFFERENTLY: video-only cannot detect that a request occurred at all (det F1
  # 0.00), audio-only detects 4 requests but grounds none (det F1 0.30, exec_time acc
  # 0.50, evidence IoU 0.25). Speech carries the existence of the event; video carries
  # its temporal anchor. Neither half completes the task.

# 9. Input media
input:
  url: https://huggingface.co/datasets/wenkai-li/agenticvbench/resolve/main/full_task_720p.mp4
        # public CC-BY re-host, attribution to "Nordic Nio VODs" (youtube:obx7hpd4ZfE)
  sha256: 1a0ca5aff0536741fe303a69bbdaaf4c2ddb8624d8df6c978b4e17336779aeb0
        # verified against the remote LFS oid; the Dockerfile sha256sum -c's this pin
  bytes: 3093147619
  layout: faststart      # moov atom at byte 32, so `ffprobe <url>` works without
                         # pulling 2.9 GB first; decoded audio verified byte-identical
                         # to the pre-remux bake at 900 s / 5745 s / 13200 s
  # VERIFIED remotely: the first 20 MB fetched anonymously with `curl --range` probe to
  # h264 1280x720 60fps + opus, duration 13686.861 s. Note that `check_task.py`'s video
  # check may report FAIL with a static ffmpeg build lacking working https — on the box
  # that produced these numbers, that ffprobe segfaults on ANY https URL, including a
  # 2 KB README. Reproduce the range-fetch above before believing a probe failure.
  length_min: 228           # window 00:10:00-03:58:00 of the 238-min VOD (13686.9 s)
  resolution: 720           # the baked and calibrated file is 1280x720; clears the >=720 floor
```

## Source-selection evidence (measured 2026-07-18)

- License verified via yt-dlp metadata: "Creative Commons Attribution license (reuse
  allowed)". 36 views at selection time (anti-recall). Raw unedited stream VOD — no
  narration, no facecam, no chat overlay (frame-verified at 3 timestamps; teammate
  visibly co-building on screen at ~02:00:00).
- Rejected alternatives and reasons: see "Source selection" in RUNBOOK.md; notably
  edited+narrated videos leak events into audio, and one candidate carried a
  stream-chat overlay (viewers narrate events — an audio-independent leak channel).
- Command density: 127 command-like caption cues across the VOD; densest 90-min
  window (00:10-01:40) holds 57.

## The audio-only ablation, in detail (measured 2026-07-30)

Transcript-only, no video: **reward 0.1111** — under the 0.15 gate, but the margin is
thin enough that the mechanism has to be stated rather than the number quoted.

What the transcript alone buys (diagnostics over the 13 of 14 utterances it located,
detection F1 0.72): action 0.92, target 0.92, executor 0.85, object 0.77, outcome 0.54,
execution start within 10 s 0.62 — and **evidence-window IoU 0.23**. Ten of the eleven
located-but-wrong rows failed on the evidence window. That window, pinned to the
on-screen execution, is what carries the defense; every other field is substantially
guessable from speech plus the closed vocabulary.

Both of its two full matches are structural, not comprehension:

1. `retry/pig_elytra_flight` — the ground-truth evidence window is 55 s wide, so a lazy
   83 s guess still scored IoU 0.66 and cleared 0.5.
2. `place/boat_half_in_wall_hole` — the one `not_done` row. Its executor is `none` and
   all three timestamps are null, so there is no video-grounded content to get wrong:
   inferring "nobody ever did it" from the absence of an acknowledgement in speech
   matches the row exactly.

Point 2 corrects an assumption made earlier in this task's design. Unexecuted commands
were expected to *defend* against audio-only models; in a command ledger they do the
opposite, because a null-valued row is free. (In the earlier mistake-timeline design
they really were a defense, since a mistake row still required a visible wrong action.)

Two task-level hardenings follow, and they are task changes, not threshold changes —
tightening TOL_EXEC from 10 s to 4 s was measured and moves the score not at all
(0.1111 throughout), and raising IOU_MIN to 0.7 does halve it to 0.0556 but that is
exactly the "fix the threshold" move this family warns against, so it was not taken:

- Define the evidence window for a long-running action as the **onset segment** (cap
  ~30 s) rather than the whole activity, stated in the prompt so honest solvers know the
  rule. Current ground-truth widths run 8-81 s (median 24).
- Keep `not_done` rows rare, or require them to carry a video-grounded anchor. This
  ledger has exactly one.

## Why speaker/target are unscored (found while building the ground truth, 2026-07-30)

Both independent annotation passes attributed the piston-scene suggestion to
"ThatDeath". Dense-frame adjudication showed the co-player standing in that room is
**NorthPickYou** (nameplate legible at window 2106 s) — and, worse, the error was
induced by the annotation prompt, which had named Death as "the recurring co-player"
and anchored both annotators.

Two conclusions were drawn rather than patched over:

1. Voice-to-name attribution is not reliably recoverable by any annotator of this
   footage (no diarization, nameplates only show who is *visible*, not who is
   *talking*), so scoring it would grade ground-truth noise. `speaker`/`target` moved
   to reported-but-unscored; the scored chain is action, object, executor, outcome,
   plus the two timestamps and the evidence window — all settled by the video.
2. Priming an annotator with "the usual co-player is X" manufactures agreement.
   Annotation prompts must name the roster only as *possibilities*, never as a
   default. Any future round must fix the prompt before it runs.

## HONEST GAP: the image has never been built end-to-end

Docker is not available on the machine that produced these numbers, and the box has
2.6 GB free against a 3.1 GB download, so `docker build` has never run against this
Dockerfile as it currently stands. What HAS been verified statically:

- every remote fetch in the build resolves — `model.bin`, `config.json`,
  `tokenizer.json`, `vocabulary.txt` from `Systran/faster-whisper-base.en`, and the
  media URL — all HTTP 200 as of 2026-08-01;
- the pinned `MATERIALS_SHA256` equals the remote LFS oid, so the build's
  `sha256sum -c` will pass;
- the calibration sandboxes carry the same `transcribe` tool and ffmpeg the image
  installs, so the measured numbers are not from a different environment.

A `docker build` on a machine with room is still REQUIRED before merge. An earlier
revision of this file fetched `preprocessor_config.json`, which does not exist in that
ASR repo, and `|| exit 1` killed every build — that class of failure is exactly what a
real build catches and static checking does not.

## Environment verification: the agent can actually hear (measured 2026-07-30)

Text+vision harnesses (Claude Code, Codex) cannot process audio, so the image ships an
offline speech-to-text tool (`transcribe`, faster-whisper base.en, CPU int8, model baked
under `/baked/asr`) — otherwise agents would score 0 for lack of a sensor rather than
for lack of reasoning, and the task would be measuring the wrong thing.

Measured on this session's audio with exactly that model:

- Throughput: 90 s of audio in 4.7 s including model load on 1 CPU → the full 5400 s
  session transcribes in roughly 5 minutes, well inside the 3600 s agent timeout.
- Recoverability: the scored commands do come through, e.g. "lead a boat. Not the big"
  (= "lead the boat, not the pig"), "stand on the hill or something", "you have to be a
  little above the boat first and only then you need to glide".
- The tool does NOT diarize, and its segments run ACROSS speaker turns (one segment
  captured coach + streamer + coach), so speaker/target attribution stays a genuine
  inference problem rather than a lookup.

## Prompt-writing rules compliance

Player, action, and object vocabularies are enumerated in the instruction (fill
during annotation). Outcome labels are closed (4). Deliverable path explicit. The
scoring method, tolerances, and ground-truth process are never revealed to the agent.
