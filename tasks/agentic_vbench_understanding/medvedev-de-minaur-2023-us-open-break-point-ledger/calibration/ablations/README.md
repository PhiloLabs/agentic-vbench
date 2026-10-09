# Anti-shortcut ablations

The canonical input is already video-only: `/workspace/materials/match.mp4` has no
audio stream. The no-media, single-frame, and scoreboard-only runs used the same
frozen instruction, oracle, model, and fixed Codex image as the full-media run; only
the input transform changed. The contact-sheet run used the same model, image, and
task files through a separate adapter. Current scores are deterministic regrades of
the retained submissions with `hierarchical-bottleneck-v1`.

| ablation | input construction | reward | exact-event diagnostic | ATIF turns | native ops | status |
|---|---|---:|---:|---:|---:|---|
| no media | remove the baked match before agent start | 0.0000 | 0.0 | 3 | 3 | agent abstained |
| one representative frame | lossless one-frame H.264 at source t=`3576.289383` s | 0.0000 | 0.0 | 7 | 9 | agent abstained |
| scoreboard graphics only | retain the cleaned score graphic and set all other pixels to black | 0.1175 | 0.0 | 65 | 60 | below 0.15 |
| all frames as contact sheets; zero calls observed | pack every decoded frame once into 179 ordered 40x30 sheets | 0.0222 | 0.0 | n/a | 0 | below 0.15; protocol acceptance pending |

The score/result fixed prior is documented separately in `../baselines/`. It is not
an agent ablation: it is granted oracle identities and outcomes. It scores `0.1833`
and is intentionally disclosed as an unresolved shortcut-risk signal.

## No media

The baked media was removed before the agent started. The manifest contains no
match-derived content. The agent inspected the workspace, stated that evidence was
absent, and did not create a submission.

```text
trial: no-media__S9MmTgi
current reward: 0.0000
predicted events: 0
```

The raw trajectory, input manifest, generation-time reward/validation, and current
hierarchical verifier details are retained with the `v11-no-media` prefix.

## Single representative frame

The transform selected source time `3576.289383` seconds and encoded one frame as
lossless H.264. It retained 1280x720 dimensions but no temporal context.

```text
trial: single-frame__WbE57Pf
input sha256: 05cb0ea84e24a151a99053da9b81a7fcf1f1d873d2bd2e23088561c39d1bb6af
input bytes: 150645
probe: H.264, 1280x720, 30000/1001 fps, 1 decoded frame, 0.033367 s
current reward: 0.0000
predicted events: 0
```

## Scoreboard graphics only

The clean v13 transform retains the temporal score graphic but replaces the court,
players, ball, and every other region with exact black. It preserves 214,363 source
frames and has no audio. Preflight checked fixed-geometry containment, lossless
decoded score pixels, black absence behavior, and removal of setup-time QA files
before the agent started.

```text
trial: scoreboard-only__ycA6hee
input sha256: 4c6012cfe5cc4756d76d64a151ce813888dc2a9026129e618483de8c683ffc76
input bytes: 107305402
probe: H.264, 1280x720, 30000/1001 fps, 214363 frames, 7152.578767 s, no audio
current reward: 0.1175
predicted events: 16
ordered identity matches: 16
```

The run shows that score graphics can recover the event-indexing layer, but the
summary/shot bottleneck keeps the official score below `0.15`. An earlier attempt
whose setup area retained oracle-derived QA files is excluded from formal evidence.

## All-frame contact sheets; zero calls observed

Every one of the 214,363 decoded source frames was placed in order into 179 JPEG
contact sheets: 40 columns by 30 rows, with each frame reduced to a 64x36 cell. The
last sheet contains 763 valid cells. Original sheets are 2560x1080; Codex CLI
preprocessing stored 2048x864 session payloads.

```text
trial: frame-dump-no-tools__uRwKB2a
original 179-sheet hash manifest sha256: 4ee2dbfef29fd9da705d5e84452c9b4b5837d06e1162edaa844356ec298b0ed1
native Codex stream sha256: 5c02facdcf4cc8397eb41d2616da139fe3e817204792304644ef76d038650fcd
full local session sha256: f6f275834e2c3f727f022eb4d0fa11d4de1b935f5bb5761e50103c4df7e46018
full local session bytes: 191878896
current reward: 0.0222
predicted events: 14
ordered identity matches: 1
observed native operations: 0
```

The retained native stream is complete. The 191 MB image-embedded session remains
local; the committed sanitized derivative replaces images, encrypted reasoning, and
account rate-limit payloads with byte-count/SHA records while preserving timeline
and operation evidence. The validator decoded all 179 preserved session images and
found zero model tool calls across the preserved operation-bearing layers.

This proves only **zero model tool calls observed in the preserved session**.
Codex CLI `0.149.1` did not expose an auditable backend `tools=[]` or
`tool_choice=none` mode for this adapter. The source-sheet to preprocessed-image
mapping was not cryptographically reconstructed after CLI preprocessing. The
downsampling and post-run audit require maintainer acceptance before this can be
described as a true tools-disabled ablation.

## Interpretation boundary

The measured no-media, one-frame, scoreboard-only, and contact-sheet conditions are
all below `0.15` under the official scorer. These experiments do not prove that
every famous-match, public-statistics, or fixed-prior shortcut fails. The deliberately
oracle-assisted fixed prior exceeds `0.15`, and the full-media strong model exceeds
`0.10`; both facts remain visible in `../scores.md`.

`SHA256SUMS` binds every retained file in this directory. The neighboring
generation-time `.reward.json` and `.validation.json` records still describe the
frozen exact judge used when the run was produced; current scores are in the
`*.hierarchical-verifier-details.json` files.
