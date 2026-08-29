# Task Spec Card — captaincook-recipe-step-transcripts

# Family: agentic_vbench_understanding. Source: CaptainCook4D (arXiv:2312.14556), Apache 2.0.
# 22 head-mounted GoPro recordings, 293.3 minutes, 314 performed recipe steps, 84 labels.

# 1. What kind of thinking does this task need?
#
# Not perception: recognising that a hand is pouring something is the easy part. What is
# scored is the transcript of a procedure as one particular person actually executed it,
# so the agent has to decide which steps happened, which did not, in what order, and
# where each one began and ended. All of those are properties of the whole recording
# rather than of any frame.
#
# The corpus is deliberately several recordings of the same few dishes: 6 dishes across
# 22 recordings, 5 of them Ramen and 5 Coffee. That is the setting in which recognising
# the dish is most tempting and least useful. Knowing the recipe for Ramen tells you
# nothing about which of its steps this person skipped, which they did twice, and which
# they did in the wrong order, and 199 of the 314 steps are annotated by the dataset as
# performed with an error.
#
# No recording can be answered from a glance and none dominates the key: the largest
# single recording holds 6.1 percent of it and the largest five hold 27.1 percent, so
# concentrating on a handful leaves most of the key on the table.

# 2. Which modalities are REQUIRED?
#
# Video only, and the video is load-bearing rather than decorative. The clips carry no
# audio track and no captions. They are NOT free of on-screen text: the tablet the study
# prompts its participants with is often in frame and its step list is legible after
# upscaling, which open item 6 states in full. An earlier version of this section claimed
# there was no on-screen text, which was wrong. The moment a step begins and the moment
# it ends still exist only in the pixels, and that is what is scored: the tablet shows
# the canonical script, worth 0.0032 as an answer, and it is the timing it does not
# supply. Nothing in the prompt says which dish any clip is, and nothing in the prompt
# says which steps a given person performed, so both have to be read off the video.

# 3. The exact question and output schema.
#
# For each of the 22 videos, return the chronological transcript of the recipe steps
# that person actually performed, one entry per performance:
#
#   {"sequence": [{"video": "A", "id": 11, "t_start": 32.5, "t_end": 61.2}, ...]}
#
#   video    one of "A".."V"
#   id       an integer from the 84-label closed vocabulary printed in the prompt
#   t_start  seconds from the start of that clip
#   t_end    seconds from the start of that clip
#
# The full prompt is steps/solve/instruction.md and is generated from the key by
# provenance/make_task_files.py, so it cannot drift from what is graded.

# 4. Evidence chain: far-apart moments the answer depends on.
#
# Every entry needs two separated observations, the moment the action starts and the
# moment it stops, and the median step here runs 27 seconds, so the two are not adjacent
# frames. Beyond that, the ordering is scored: the alignment is order-preserving within
# a video, so an entry placed correctly but reported after an entry that belongs later
# costs a match. That makes the answer for one recording a single chain rather than 15
# independent judgements.
#
# Across recordings the chain is longer still. Five recordings are the same dish. An
# agent that transcribes one and reuses it for the next four scores on the steps they
# happen to share and loses on the errors, skips and reorderings that differ, which is
# what the eligibility gate below guarantees exists in every recording.

# 5. Ground truth: value, source, tier, verification.
#
# Tier: released human annotation, transformed mechanically. Nothing is authored here.
#
# Source: CaptainCook4D's `complete_step_annotations.json` and `error_annotations.json`,
# pinned by commit in provenance/data_setup/01_download_annotations.sh. Every label,
# boundary, dish name and error flag comes out of those files.
#
# The transform is provenance/build_gt.py. It refuses to emit a key unless it passes:
#
#   - the per-step has_errors flag agrees with the separate per-recording error file on
#     all 384 recordings (it does: 164 clean, 220 with errors, zero disagreements)
#   - every emitted instance lies inside its video and the list is chronological
#   - the shipped judge returns 1.0 on the key and 0.0 on the empty submission
#
# Three properties of the source cost real time to find and are enforced rather than
# described:
#
#   1. A skipped step is annotated with start_time = end_time = -1. 287 rows across 141
#      recordings look like this. They did not happen, so they cannot appear in a
#      transcript of what happened; sorting them by start time would file them all
#      before the first real step and hand the agent an unanswerable entry at t = -1.
#      build_gt.py drops them and prints the count.
#   2. step_id is not a global label. Three ids are reused across dishes for different
#      steps, and step_idx_description.json stores only one text per id. The label is
#      therefore (activity_id, step_id).
#   3. Even keyed that way, four dishes annotate one (activity_id, step_id) with two
#      different texts across recordings, so the id does not identify the step within
#      those dishes either. Those four are excluded whole rather than patched, because
#      patching would put us in the business of authoring labels. That costs 69 of the
#      384 recordings and is printed on every build.
#
# Corpus selection is provenance/take_selection.py, which states the rules, re-derives
# the pool independently of the shipped key, and exits non-zero if the rule no longer
# produces the shipped corpus.

# 6. Scorer: deterministic code only.
#
# steps/solve/tests/judge.py, pure stdlib, no network, no model. A predicted entry is a
# true positive only when it names the right video, its label matches, and BOTH
# boundaries fall inside that step's own tolerance, under an order-preserving one-to-one
# alignment within that video (an LCS-style DP). Tolerance is a quarter of the step's
# annotated duration, floored at 1 s and capped at 3 s, applied to both boundaries. The
# reward is F1 over the totals, so misses and false positives both cost. The judge is
# generated from the key by provenance/make_judge.py.
#
# ONE DELIBERATE DIVERGENCE from the Ego-Exo4D task this scorer was copied from. Before
# aligning, the judge sorts each video's entries by (onset, label). Without that, the
# key's arbitrary order among steps that begin at the same second became a requirement
# the prompt never states and the video cannot reveal: U has two steps that both start at
# 455.647, and submitting them the other way round dropped a perfect oracle to 0.9968.
# The prompt now states the same rule, so an agent can produce the canonical order
# itself. A consequence worth naming rather than burying: because the submission is
# canonicalised first, the POSITION of a row in the submitted list no longer carries any
# information. Order is carried by the timestamps, which is what the prompt asked for all
# along, and the alignment still refuses to match two steps whose times are in the wrong
# sequence. provenance/test_judge_contract.py covers both, each with a control that must
# fail.

# 7. Difficulty: measured with real strong-agent runs.
#
# See calibration/scores.md. The family's two gates are that a strong agent scores below
# 0.10 and that a real attempt runs past 50 tool-call turns.

# 8. Anti-shortcut ablations. Target: each <= 0.15. Measured, all far below.
#
# Three of these are real runs of a strong model under degraded input, not simulations:
# gpt-5.6-sol at xhigh, each in its own empty working directory so that nothing but the
# attached images was reachable, prompts derived from the shipped one by
# provenance/ablations/make_ablation_prompt.py (which asserts all 84 vocabulary rows
# survive), transcripts and answers under provenance/ablations/measured/. Every one of
# the three ran with ZERO shell commands, which the retained transcripts show.
#
#   degraded input                              entries  label+order   F1
#   no media at all, forced to answer               352           32   0.0
#   one still per recording, no tools               326          161   0.0031
#   16 uniform frames per recording, no tools       312          211   0.0032
#
# All three are forced to answer. A refusal also scores 0.0, but a zero from a model that
# declined to guess says nothing about whether the degraded input was enough, and an
# earlier single-frame run did exactly that.
#
# The last row is the most informative number in this file. Handed 16 frames per
# recording and no way to ask for more, the model matched 211 of the 314 steps by label
# in the right sequence position, MORE than any calibrated agent managed with the full
# video and tools, and scored 0.0032. Recognising the procedure is not what this task
# pays for, and seeking through the video is not optional.
#
# The deterministic constructions, recomputable with run_ablations.py:
#
#   oracle, the key itself                                        1.0
#   empty submission                                              0.0
#   canonical recipe prior, full dish order                       0.0032
#   canonical recipe prior, labels that occur only                0.0065
#   random submission, mean of 400 draws                          0.0001
#   random submission, best of 400 draws                          0.0032
#   spam, canonical cycle at 0.5 s stride                         0.0005
#   spam, canonical cycle at 2 s stride                           0.0013
#   spam, entry-cap pack of 20000 at 0.5 s stride                 0.0005
#   spam, top-5 per-recording labels at 2 s stride (upper bound)  0.0007
#   oracle answers filed under the wrong video                    0.0
#
# Reciting the canonical recipe is the strategy an agent that recognises the dish would
# reach for, and it scores 0.0032. The spam row is the standard attack on an
# order-preserving alignment; F1 charges for every entry that does not match, so flooding
# cannot pay, and the best spam of any kind reaches 0.0013. The top-5 row is handed the
# labels that actually occur most often in each specific recording, which a real attacker
# could not know, so it is an upper bound rather than a strategy. Audio-only and
# video-only do not apply: the clips carry no audio track.

# 9. Input media.
#
#   count: 22 continuous head-mounted GoPro recordings, 10.0 to 19.2 minutes each
#   total: 293.3 minutes, inside the family's 10-to-300-minute window
#   resolution: 1080p, downscaled from the published 3840x2160 HEVC source
#   audio: dropped at bake time; the task is video-only
#   hosting: see the open item below
#   licence: Apache 2.0, which permits redistributing the downscaled derivative with
#            attribution. NOTICE carries it.

## Open items flagged for review

1. **Media hosting, now settled, and open only in the sense that a maintainer may want
   it elsewhere.** The publisher's own 4K objects are public and ungated at
   data.utdallas.box.com, which is what made this source viable at all, but the 22 of
   them are about 88 GiB and decoding 4K HEVC inside an image build is hours of CPU.
   The image therefore pins a 1080p derivative. Apache 2.0 permits that redistribution
   and NOTICE travels with the media.

   The derivatives are published at
   huggingface.co/datasets/Maxine668/captaincook-recipe-step-transcripts and
   environment/Dockerfile pins that prefix. Verified end to end on one recording:
   download, SHA256 match against provenance/media_manifest.json, and bake to a single
   1920x1080 video stream with no audio, metadata or chapters.

   provenance/media_manifest.json records for every letter both the publisher's URL and
   the SHA256 of the publisher's own object alongside the derivative's, so a reviewer
   can verify the derivative was made from the real source and rerun
   provenance/data_setup/02_prepare_media.sh. On reproducibility: what a rerun of provenance/data_setup/02_prepare_media.sh reproduces is
   the same content from the same verified source, not the same bytes: the encode runs on
   h264_videotoolbox, a hardware encoder, and its output is not guaranteed identical
   across machines or OS versions. What IS pinned byte for byte is the artifact the image
   actually bakes, by the derivative SHA256 in the manifest, which environment/bake.sh
   verifies and refuses to proceed without. Rerunning the script with the committed
   manifest present makes it CHECK each digest against the manifest rather than only
   record a new one, and it says so per file. If the
   maintainers would rather host it themselves, one run of provenance/make_dockerfile.py
   with a different --base rewrites the Dockerfile and nothing else changes.

2. **Resolution.** The source is 4K and the shipped copy is 1080p. That is above the
   720p bar this family's egocentric proposals have been held to, but it is a
   downscale, and it is stated here rather than left to be discovered.

3. **The corpus is 6 dishes, not 20.** R4 walks recording_id in ascending order, and
   that order groups by dish, so the corpus lands on 6 dishes with 3 to 5 recordings
   each. A one-recording-per-dish rule would give 17 dishes and a 270-label vocabulary
   instead of 84. It was written, run, and dropped because nothing but our own
   preference selects it, which makes it a knob; see the note in
   provenance/take_selection.py. It was never scored against an agent. A reviewer who
   thinks vocabulary breadth matters more than un-tunability should say so and it will
   be changed before merge rather than after.

4. **The eligibility criterion changed from the Ego-Exo4D version of this task.** That
   version required at least 3 repeat instances; this one requires at least 3 steps
   annotated as performed with an error. Both exist to guarantee that replaying the
   canonical script cannot score. CaptainCook4D steps almost never repeat, its median
   recording repeats no step at all, so the repeat criterion would admit 3 of its 384
   recordings. The criterion was replaced rather than relaxed and the threshold of 3
   was carried across rather than re-chosen, but it is a change and it is flagged.

5. **Tolerance sits at its cap more often than in the Ego-Exo4D version.** The steps
   here run 27 seconds at the median against 7 seconds there, so 82 percent of
   instances are graded at the 3-second cap rather than on the quarter-duration rule.
   The tolerance rule itself is unchanged, and moving it would be exactly the kind of
   difficulty tuning this family warns about, so it was not moved. What this buys the
   agent is measured: with perfect labels and perfect ordering, Gaussian boundary noise
   of sigma = 5 s still scores 0.183 here against 0.107 on the Ego-Exo4D key, both
   recomputed by the same routine, so this key is about 1.7x more forgiving on timing
   alone. Reproduce ours with `run_ablations.py --jitter`; three decimals is all the
   precision the estimate has. That factor is the reason the calibration in
   calibration/scores.md is the deciding evidence rather than a formality.

6. **There is a tablet in shot, it is showing the step list, and the step text is
   legible.** CaptainCook4D prompts its participants with the step list on a tablet
   propped on the counter, and because the camera is head-mounted the tablet is in frame
   a lot: in a 12-frame sample spread across one 13-minute recording it appears in 10,
   and it appears in three of four recordings sampled from different dishes, kitchens and
   participants. It is the study's standard apparatus, not one participant's setup. This
   was found by looking at the baked media rather than reported by the source.

   **An earlier version of this item said the step text "is not readable at any angle
   sampled". That was wrong, and the correction is the reason this item is now the
   longest one here.** At native 1080p the text is a smear. Upscaled 2x, which is what an
   agent extracting frames would do, several lines are plainly readable, and what they
   read are the key's own label strings verbatim, including the doubled prefixes
   ("add-Measure ...", "Sprinkle-Sprinkle ...") that are an artefact of how this task
   builds label text out of the dataset's fields. The screen shows a scrollable list of
   the steps in canonical order, not one step at a time.

   So the honest statement of the cue is: **an agent that reads the screen gets the label
   set and the canonical order for free.** It does not have to infer which of the 84
   labels apply to this recording.

   What that is worth is already measured, and it is the number this item turns on.
   Replaying the canonical order is the ablation at the top of section 8: **0.0032**. The
   screen supplies labels and order; the score is almost entirely boundaries, and the
   screen does not supply boundaries.

   The list's scroll position is a live pointer and is not bounded by that number, so it
   was measured separately. **That measurement was inconclusive and is reported as
   inconclusive.** Two automatic screen detectors were written and both were discarded
   rather than shipped: a brightness-percentile one that reported a screen in 100 percent
   of frames including frames of a wall and a sink, and a connected-component one that
   then rejected every frame in which a tablet was plainly visible. A hand reading of
   nine frames across three step boundaries in one recording could not separate the page
   scrolling from the tablet's distance and angle changing in a head-mounted view: at
   t=470 three lines are visible and at t=495 five are, and that is as consistent with the
   camera moving closer as with the page moving. What can be said is that at t=495 the
   step the person was actually performing sat at the top of the visible list, so the top
   of the list is at least a coarse pointer.

   The cost of that pointer can be looked up rather than argued. If an attacker recovered
   every boundary from the scroll with Gaussian error, section 7's jitter curve gives the
   score: 0.183 at sigma = 5 s, 0.077 at 8 s, 0.051 at 10 s and 0.023 at 15 s. A pointer
   would have to be good to about 5 seconds to threaten the 0.10 gate, on a cue whose own
   transitions we could not localise to better than tens of seconds. And that is an
   optimistic model for the attacker, because the list is the canonical script: it cannot
   say which steps this person skipped (287 prompted steps across the release were skipped
   outright), which they performed out of the induced order (77 inversions here), or which
   they got wrong (199 of the 314 steps are annotated as errors).

   **What three strong agents actually did with it.** Antigravity noticed the tablet in
   the very first frame it looked at, writing "I see a tablet on the counter displaying
   text, potentially recipe instructions", and then never referred to it again across 426
   tool calls. Codex never mentioned it. Claude never mentioned it. None of the three
   attempted to read it, and the best of them scored 0.0762. The cue is real and it is
   available; it is not currently being taken.

   Two things a reviewer should know we did NOT do. We did not blur or crop the tablet:
   that would be editing the source material, and it would also remove a cue a person
   watching the video would have. And we did not build a working tablet detector, so the
   scroll-as-timing channel remains the one open measurement on this task. If a future
   agent scores near the gate, that is where to look first.
