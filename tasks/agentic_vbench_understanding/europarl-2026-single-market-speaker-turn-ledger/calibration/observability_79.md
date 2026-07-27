# Full-roster observability audit

Issue #58 review requires a frames-next-to-portraits check across the complete
79-person roster.

## Method

For each anonymous roster ID, the audit selected five candidate frames from that
speaker's first scored turn. OpenCV YuNet detected visible faces and SFace ranked
the selected face against all 79 official portraits. The highest-confidence
candidate was paired side by side with its portrait and manually reviewed.

## Results

- Candidate video frame found: **79/79**
- Correct portrait ranked first among 79: **79/79**
- Passed the conservative SFace cosine threshold: **78/79**
- Manual identity match: **79/79**
- Manual visibility category A or B: **79/79**

The one threshold miss (`speaker_017`) still ranked the correct portrait first
with a large margin and was manually confirmed. No lookalike substitution was
observed.

## Artifacts

- `observability_79.json`: anonymized per-speaker frame time, automated 79-way
  portrait-match rank, similarity, and manual visibility classification.
- Private review contact sheets pair each anonymized official portrait with the
  selected video frame. They are generated from the shipped materials and are not
  duplicated in git.
