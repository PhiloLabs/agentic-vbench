# Independent annotation and adjudication

The original six-field clean-room process and the dismount-takeoff extension
are complete. The second annotation was performed by a human who did not create
or inspect the draft ground truth.

## 1. Blind second pass

Give reviewer 2 only:

- the source video whose SHA-256 is
  `7dfc9e139254cc9480948af734988bdebc796c89c6e5d439055a248c251130cb`;
- the routine-boundary rules copied below; and
- a fresh copy of `reviewer-2.template.csv`.

Do not give reviewer 2 repository access, the current ground truth, FineGym
annotations, candidate timestamps, the routine count, or old calibration
artifacts.

Reviewer 2 must scan the full 139.3-minute video. For every complete live
foreground balance-beam routine, record the first visible mount takeoff or
intentional weight transfer and the first frame of landing-mat foot contact
after the final dismount. Exclude replays, warm-ups, and incomplete or background
performances.

Save the completed sheet as `reviewer-2.raw.csv`. Record the annotator identity
internally, plus the date, video digest, and an explicit statement that the pass
was blind in the comment rows at the top of the file. Do not publish the
reviewer's name or contact information.

## 2. Adjudication

Only after reviewer 2 submits the sheet, give the adjudicator the draft ground
truth, `reviewer-2.raw.csv`, the source video, and
`adjudication.template.csv`.

The adjudicator must account for every routine in either source and inspect the
video for every count or boundary disagreement. Record both proposed boundaries,
the final boundary, the visible representing school, gymnast name, official
individual beam score, the first time the score is readable or derivable, and a
short video-based decision. Use only `Stanford`,
`Arizona State`, `Oregon State`, or `Arizona` for the school label. Canonicalize
scores to three decimal places so trailing zeroes are preserved. The final
chronological rows become both
`steps/solve/tests/ground_truth.json` and
`steps/solve/solution/solution.json`.

The canonical `adjudication.csv` begins with the adjudicator role, adjudication
date, and source-video SHA-256 required by `adjudication.template.csv`. The
identity-safe role label is used for publication. The exact pre-header file used
by the final calibration runs remains local as
`private/adjudication.pre-publication.csv`.

## 3. Release gate

Update `status.json` only after:

- the blind second-pass sheet is complete;
- every difference is adjudicated;
- both final JSON files are identical;
- the verifier unit tests pass; and
- SHA-256 hashes of the two raw CSV files are recorded.

Set `state` to `complete`. Do not start the three strong-agent runs while it is
`pending_second_annotation` or `pending_dismount_takeoff_annotation`. Keep the
raw CSV files unchanged locally for review.

## 4. Dismount-takeoff extension

The Google Sheet added `Dismount takeoff time` and `Dismount takeoff note`.
For each of the 23 included rows, the reviewer recorded the first approximate
time when the gymnast's final support foot loses contact with the beam for the
final dismount. Excluded candidate `R2-015` is `N/A`.

The reviewer entered nearest-second estimates. Adjudication inspected every
estimate at the source's 30000/1001 fps cadence and selected the first frame
after final foot or toe contact. For connected roundoff or back-handspring
dismounts, this is the final rebound launching the airborne dismount, not the
earlier entry into hand support. `dismount_takeoff_time` is now part of the
scored JSON with a ±0.25-second tolerance.

The local `dismount-takeoff-reviewer.raw.csv` preserves the pre-adjudication
Google Sheet values. `adjudication.csv` records the exact-frame results. The
release gate may open only after both artifacts are hashed and the oracle and
tests pass.

## Completed artifacts

- `reviewer-2.public.csv` preserves the independent reviewer's 2026-08-26
  Google Sheet values, including blank cells, with only the reviewer identity
  replaced by a role label.
- `dismount-takeoff-reviewer.public.csv` preserves the independent reviewer's
  nearest-second takeoff estimates before frame refinement, with the same
  identity-only replacement.
- `reviewer-seven-field-update.public.csv` is an immutable CSV rendering of
  the reviewer-updated Google Sheet range `A10:M34`, captured at
  `2026-08-27T18:17:17.487Z`. It preserves the exact 25-by-13 cell matrix,
  including blank cells, score formatting, row order, and the two trailing
  spaces in the six `Arizona  ` cells. The captured TSV bytes hash to
  `ea1c7ee6c653b9a890676fa1f1eaf18a4c796ace0ffefa77deed596b73384db6`;
  the public CSV hashes to
  `c9c193a7bfae09625f44581f69216b57ff7e7eee0dd55e7b9010a170969993b6`.
  The captured range contains no annotator identity field. This is
  post-adjudication reviewer provenance, not a retroactive calibration input.
- `adjudication.csv` accounts for all 24 reviewer candidates. Twenty-three are
  included; the 01:20:00 candidate is excluded because the broadcast enters
  mid-routine and never shows its mount.
- The reviewer's updated Google Sheet supplies a school label for every row:
  Stanford (6 included), Arizona State (6), Oregon State (5 included plus the
  excluded candidate), and Arizona (6).
- The same update supplies the gymnast name and official beam score for every
  row, plus a score-availability time for every directly displayed score. The
  scored key retains all 23 included name/score pairs and canonicalizes scores
  such as `9.8` and `9.85` to `9.800` and `9.850`.
- For each school's sixth gymnast, the broadcast never shows another individual
  score graphic. Adjudication derives that score from the completed beam
  subtotal and assigns the first readable subtotal frame as `score_time`.
- Every accepted start and end was checked against source frames and snapped to
  an exact source-frame presentation timestamp. Ends use the first landing-mat
  foot-contact frame, not the later stabilization or salute.
- Every included dismount takeoff was frame-adjudicated; the excluded candidate
  has no scored takeoff.
- `status.json` records the public artifact hashes, retains the exact
  hashes and filenames of the local calibration inputs, and marks the release
  copy as a post-run privacy-only derivative.

## Publication privacy and provenance

The calibration gate and all three final agent runs used the status now
preserved locally as `private/status.pre-publication.json`, together with
`reviewer-2.raw.csv` and `dismount-takeoff-reviewer.raw.csv`. Their original
SHA-256 values are retained in the canonical public `status.json`. The private
status and raw CSVs remain local and are excluded from publication.

The two identity-redacted `.public.csv` files differ from their raw sources
only in the annotator comment. All header names, candidate rows, blank cells,
timestamps, notes, and row order are byte-for-byte identical after that comment
is removed. The seven-field public CSV is a deterministic format conversion of
the identity-free sheet range; parsing the captured TSV and public CSV produces
the same ordered cell matrix.

The public `status.json` replaces the two annotator fields, points its active
artifact fields at the public CSVs, adds the reviewer-updated seven-field
evidence, and retains every calibration-input filename and hash. The three
required identity-safe metadata lines added to `adjudication.csv` are also
recorded as a post-calibration provenance-only delta. This keeps a fresh
checkout usable by the calibration runpack.
`publication-redaction-audit.json` binds every source and destination by
digest and records the exact replacements and metadata additions.

This privacy-and-provenance package was created after calibration. It did not
alter the task prompt, staged video, scorer, ground truth, submitted solutions,
or any frozen run input manifest. Gymnast names remain because they are visible
broadcast labels required by the scored task; they are not annotator identity
data.
