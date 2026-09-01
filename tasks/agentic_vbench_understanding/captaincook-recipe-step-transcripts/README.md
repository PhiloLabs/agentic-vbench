# captaincook-recipe-step-transcripts

An agent watches 22 continuous head-mounted GoPro recordings, 293.3 minutes in total, of
people cooking in real kitchens. For each recording it must return the transcript of the
recipe steps that person **actually performed**: the label of each step, in the order it
happened, with the second it began and the second it ended. 314 performed steps across
the 22, drawn from a closed vocabulary of 84 labels covering 6 dishes.

The point of the corpus is that these are not clean executions. CaptainCook4D recorded
people making deliberate mistakes, and it annotates them: 199 of the 314 steps are
flagged as performed with an error, the recordings depart 77 times from the step order
induced by the other recordings of the same dish, and 287 steps across the release are
annotated as skipped outright. Five of the 22 recordings are Ramen and five are Coffee,
so an agent that recognises the dish and recites its recipe has recognised nothing that
scores. Reciting that recipe, in the strongest form available (the order induced
leave-one-out from the other recordings of the same dish), scores **0.0032**.

## Layout

```
task.toml                            generated from the key
NOTICE                               Apache 2.0 attribution for the media
SPEC.md                              the spec card, including the open items
environment/Dockerfile               generated; bakes the 22 recordings by SHA256
environment/bake.sh                  fetch, verify, strip metadata, assert clean
steps/solve/instruction.md           generated; the prompt the agent sees
steps/solve/solution/solve.sh        generated; the oracle, scores 1.0
steps/solve/tests/judge.py           generated; pure stdlib, carries the key
provenance/data_setup/01_...sh       fetch the annotations, pinned by commit
provenance/data_setup/02_...sh       build the 1080p media package
provenance/build_gt.py               annotations -> step-derived.json, with the guards
provenance/take_selection.py         states R1-R5, re-derives the pool, asserts agreement
provenance/verify_key.py             re-derives the key WITHOUT build_gt and compares
provenance/test_oracle_integration.py  RUNS the shipped oracle, grades what it wrote
provenance/audit_error_observability.py  the checkable half of the observability audit
provenance/observability/            per-tag evidence that the error field is visible
environment/frozen.json              base digest, image id, and the 22 baked hashes
environment/verify_frozen.py         checks a built image against that record
provenance/make_judge.py             step-derived.json -> judge.py
provenance/make_task_files.py        step-derived.json -> prompt, task.toml, oracle
provenance/make_dockerfile.py        step-derived.json + media manifest -> Dockerfile
provenance/ablations/run_ablations.py  every guessing number the docs claim
provenance/step-derived.json         the key
provenance/media_manifest.json       per file: publisher URL, publisher SHA256, ours
calibration/                         the harness, the rollouts and scores.md
```

Rebuild the whole thing from nothing:

```
sh provenance/data_setup/01_download_annotations.sh ./cc4d
python3 provenance/build_gt.py --cc4d ./cc4d --out provenance/step-derived.json
python3 provenance/make_judge.py --derived provenance/step-derived.json \
    --core provenance/_judge_core.py.part --out steps/solve/tests/judge.py
python3 provenance/ablations/run_ablations.py
python3 provenance/make_judge.py --derived provenance/step-derived.json \
    --core provenance/_judge_core.py.part --out steps/solve/tests/judge.py
python3 provenance/make_task_files.py --derived provenance/step-derived.json \
    --media provenance/media_manifest.json --root .
python3 provenance/take_selection.py --cc4d ./cc4d --derived provenance/step-derived.json
python3 provenance/verify_key.py --cc4d ./cc4d --task .
python3 provenance/test_oracle_integration.py
python3 provenance/audit_error_observability.py --cc4d ./cc4d
```

`make_judge.py` runs twice on purpose: the judge's docstring quotes the ablation numbers,
and the ablations need a judge to run against. `run_ablations.py` refuses to run against a
judge built from an older key, because that happened once during development and the
numbers it produced looked entirely plausible.

`test_oracle_integration.py` runs the oracle that ships in the image, `solve.sh`, and
grades the `solution.json` that run writes. It exists because review round 2 found the
shipped oracle scoring 0.0 while every check that claimed to grade "the oracle" was
grading an error-aware one it had built out of the key in memory. Reading the SEQUENCE
literal back out of the script would have repeated that mistake one level down, so the
script is executed, either natively where `/workspace` is writable or inside a container,
and a run that cannot happen fails rather than passes. Its control strips the error field
from a copy of the same script and requires that copy to fall short of 1.0.

`audit_error_observability.py` recomputes the structural half of the error-field
observability audit; the half that needs eyes is in `provenance/observability/`.

`verify_key.py` is the independent check. build_gt.py writes the key and make_judge.py
copies it, so a bug in that code is invisible to both; verify_key.py re-reads the raw
annotation JSON, rebuilds what the judge should hold without importing build_gt, and
compares. It also checks that the prompt offers exactly the labels the judge grades and
that the durations the prompt advertises match the key. All three checks were confirmed
to fail on an injected error rather than merely to pass.

## Scoring rule (one coherent rule)

A predicted entry is a true positive only when it names the right video, its label
matches, and **both** boundaries land inside that step's own tolerance, under an
order-preserving one-to-one alignment within that video. Tolerance is a quarter of the
step's annotated duration, floored at 1 s and capped at 3 s, applied to both boundaries.
The reward is F1 over the totals, so a miss and a false positive cost the same.

Three consequences worth stating, because each one is a shortcut that does not work:

- **Ordering is scored.** The alignment is order-preserving, so an entry that is right
  but reported after an entry belonging later costs a match.
- **The video field is load-bearing.** Filing the oracle's own answers under the wrong
  video scores **0.0**.
- **Flooding cannot pay.** F1 charges for every entry that does not match. The best spam
  of any shape reaches **0.0013**, including one handed the labels that actually occur
  most often in each specific recording, which no attacker could know.

## Ground-truth provenance (fully mechanical)

Nothing here is authored. `build_gt.py` reads the released annotations and refuses to
emit a key unless three things hold: the per-step `has_errors` flag agrees with the
separate per-recording error file across all 384 recordings, every emitted instance lies
inside its video and the list is chronological, and the shipped judge returns 1.0 on the
key. Three traps in the source are handled rather than hoped away, and each one is
printed on every build:

1. **287 annotated steps have `start_time = end_time = -1`.** They were skipped. They
   did not happen, so they are not in a transcript of what happened, and sorting them by
   start time would file all 287 before the first real step.
2. **`step_id` is not a global label.** Three ids are reused across dishes for different
   steps. The label is `(activity_id, step_id)`.
3. **Four dishes annotate one `(activity_id, step_id)` with two different texts.** The
   id does not identify the step there either, so those four dishes are excluded whole,
   which costs 69 of the 384 recordings. Patching the texts would mean authoring labels.

## How the corpus was selected

The rules are stated in `provenance/take_selection.py`, which re-derives the pool
independently and exits non-zero if the rule no longer produces the shipped corpus. They
are the Ego-Exo4D task's rules in this family with one criterion substituted:

- **R1** no recording under 10 minutes, which is the family's own floor
- **R2** the dish must be one where the step text is a function of the step id
- **R2b** the 4K stream must actually have been published (18 are not)
- **R3** at least 3 steps annotated as performed with an error, and at least 2 departures
  from the canonical order of the dish
- **R4** ascending `recording_id`, adding until the next would pass the family's
  300-minute ceiling, then **stop**, so the rule cannot be tuned by skipping
- **R5** presented in that same order, checked rather than assumed: rank correlates
  +0.001 with duration over the 93 eligible recordings and -0.123 over the 22-recording
  prefix, and a permutation test puts a prefix correlation that large at 58.1 percent by
  chance

R3 is the one substitution. The Ego-Exo4D version asked for 3 repeat instances; this asks
for 3 error steps. Both exist to guarantee that replaying the canonical script cannot
score. CaptainCook4D steps almost never repeat, its median recording repeats no step at
all, so the repeat criterion would admit 3 of its 384 recordings. The criterion was
replaced rather than relaxed and the threshold of 3 was carried across.

## Media

The publisher's own objects are public and ungated at `data.utdallas.box.com`, which is
what made this source viable, but the 22 of them are about 88 GiB of 3840x2160 HEVC and
decoding that inside an image build is hours of CPU. The image therefore pins a 1080p
derivative. CaptainCook4D is Apache 2.0, which permits that; `NOTICE` carries the
attribution and states exactly what was changed.

The derivatives are published at
`huggingface.co/datasets/Maxine668/captaincook-recipe-step-transcripts`, and
`environment/Dockerfile` pins that prefix and each file's SHA256. Verified end to end on
one recording: download, checksum match, bake to a single 1920x1080 video stream with no
audio, metadata or chapters. `provenance/media_manifest.json` records for every letter
both the publisher's URL and the SHA256 of the publisher's own object, so a reviewer can
pull the 4K original, confirm our source was the real one, and rerun
`02_prepare_media.sh` to reproduce the derivative. That rerun reproduces the same
content from the same verified source rather than the same bytes, because the encode runs
on a hardware encoder whose output is not identical across machines; what is pinned byte
for byte is the file the image bakes, by the SHA256 `bake.sh` verifies. Rerunning with the
committed manifest present makes the script check each digest against it. Hosting it elsewhere is one run of
`make_dockerfile.py` with a different `--base`.

## Known weaknesses, stated rather than left to be found

- **The corpus is 6 dishes, not 20.** Ascending `recording_id` groups by dish. A
  one-recording-per-dish rule gives 17 dishes and a 270-label vocabulary instead of 84;
  it was written, run, and dropped because nothing but our own preference selects it.
  It was never scored against an agent.
- **There is a tablet in shot showing the recipe, and its text is legible.**
  CaptainCook4D prompts participants with the step list on a tablet, the head-mounted
  camera catches it often, and it is in three of four recordings sampled across different
  dishes and kitchens. At native 1080p the text is a smear; upscaled 2x, which is what an
  agent extracting frames does, several lines read back as the key's own label strings
  verbatim, in canonical order. An earlier draft of this bullet said the text was not
  readable, which was wrong. What it is worth is bounded and measured: replaying the
  canonical order is the ablation at 0.0032, because the screen gives labels and order
  while the score is almost entirely boundaries. The list's scroll position is a live
  pointer that is not bounded by that number, and our attempt to measure it was
  inconclusive; the jitter curve puts the price of a pointer good to 10 s at 0.051. Of
  three strong agents, one noticed the tablet in its first frame and never returned to
  it, and none tried to read it. We did not blur it, because that would be editing the
  source. SPEC.md open item 6 has the full statement, the discarded detectors included.
  The error field, added later, was audited against this same screen and does not
  appear on it: `provenance/observability/` reads the tablet at native resolution in
  two kitchens and finds the step texts and a highlight, no error wording, and none of
  the 352 released step descriptions is phrased as an error instruction.
- **The key is more forgiving on timing than the Ego-Exo4D version.** Steps here run 27
  seconds at the median against 7 there, so 82 percent of instances are graded at the
  3-second cap. With perfect labels and perfect ordering, Gaussian boundary noise of
  sigma = 5 s still scores 0.183 here against 0.107 there, both by the same routine. The
  tolerance rule was not moved to compensate, because moving it is the tuning this family
  warns about. The calibration is therefore the deciding evidence, not a formality.
