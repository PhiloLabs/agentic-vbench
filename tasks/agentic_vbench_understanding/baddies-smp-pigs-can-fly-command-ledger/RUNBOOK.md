---
title: Build log — baddies-smp-pigs-can-fly-command-ledger
summary: How this task was sourced, annotated, baked and calibrated, including the alternatives that were measured and rejected.
read_when: Judging whether this task's ground truth and calibration numbers can be trusted, or picking the task up to revise it.
---

# Build log

Everything below happened; nothing here is a plan. Measured outcomes live in
`SPEC.md` (design card) and `calibration/scores.md` (the numbers).

## Source selection — the alternatives that were rejected

1. **HoloAssist, disqualified by measurement.** The released mp4 is 896×504, under
   the family's 720p floor — verified across all 1758 sessions by ranged tar
   extraction plus `ffprobe`, not by reading the dataset card. This is why the task
   is found footage rather than an existing annotated corpus.
2. **Runner-up VOD `S1VbbvxEwv8`, rejected on leak grounds.** It carries a facecam,
   an F3 debug overlay, and a live stream-chat overlay. Stream chat is an answer-leak
   channel: viewers narrate what is happening on screen.
3. **Selected: `obx7hpd4ZfE`** — "Baddies SMP | Pigs can fly | VOD" (Nordic Nio VODs).
   CC-BY per yt-dlp metadata, 1080p, 238 min, 36 views at selection time; a raw stream
   with live voice chat, clean first-person POV, no facecam, no chat overlay
   (frame-verified at three timestamps, teammates visibly on screen).

## Baked window

`00:10:00–03:58:00` — 228 min, re-encoded to 1280×720, 3.09 GB, remuxed to faststart
so the hosted URL is probeable without a full download, sha256 `1a0ca5af…6779aeb0`,
pinned and `sha256sum -c`'d in `environment/Dockerfile`. Re-derivable at any time:
yt-dlp 1080p → `ffmpeg -ss 600 -to 14280 -c:v libx264 -crf 20 -c:a copy` → scale to
720p → `-c copy -movflags +faststart`.

The window grew from an initial 90 min to 228 min mid-build, to enlarge the ledger.
That did not have the intended effect — see the difficulty verdict in `SPEC.md` §7.

## Ground truth

178 candidates screened in three passes (regex over ASR, agent recall sweeps over the
full transcript, and a targeted deferral sweep with frames at BOTH ends of the gap),
double-annotated by two vision models, adjudicated from dense frame sampling under
`media/annotation/ADJUDICATION_RUBRIC.md`, then reviewed end-to-end by the contributor.
21 rows survived. Per-row frame citations: `steps/solve/tests/ground_truth_provenance.json`.

The annotation workbench that produced all of this — frame packets, per-candidate
rulings, solver sandboxes and logs — is ~7 GB and is gitignored under `media/`.

## Discipline notes worth keeping

- **Fix the task, not the threshold.** When the audio-only ablation looked too strong,
  the response was to change what the task asks for (deferred requests only), not to
  narrow `TOL_EXEC` or `IOU_MIN` until the number moved.
- **A prompt leak was found and every affected run was discarded**, not re-scored: an
  earlier `instruction.md` used a real ground-truth row as its worked example, and one
  agent copied it verbatim for a free true positive. The example is now fictional and
  flagged as such. Discarded logs are kept under `media/annotation/logs_leaked/`.
- **Rows were not added to move a number.** A gap-fill sweep was run specifically to
  enlarge the ledger; most of its candidates were rejected on the evidence, and the
  ledger stayed where the evidence left it.
