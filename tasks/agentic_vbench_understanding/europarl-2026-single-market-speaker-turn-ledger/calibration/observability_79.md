# Full-roster observability audit

Issue #58 review requires a frames-next-to-portraits check across the complete
79-person roster.

## Method

For each scored anonymous roster ID, the audit selected five candidate frames from
that speaker's first scored turn. OpenCV YuNet detected visible faces and SFace
ranked the selected face against all 742 usable official portraits, including 663
non-speaking distractors. The highest-confidence
candidate was paired side by side with its portrait and manually reviewed by one
reviewer as an observability check, not as the source of identity ground truth.

## Results

- Candidate video frame found: **79/79**
- Correct portrait ranked first among 742: **79/79**
- Passed the conservative SFace cosine threshold: **79/79**
- Manual identity match: **79/79**
- Manual visibility category A or B: **79/79**

No lookalike substitution was observed. The complete audit was regenerated after
the media-anchor correction.

## Artifacts

- `observability_79.json`: anonymized per-speaker frame time, automated 742-way
  portrait-match rank, similarity, and manual visibility classification.
- Private review contact sheets pair each anonymized official portrait with the
  selected video frame. They are generated from the shipped materials and are not
  duplicated in git.
