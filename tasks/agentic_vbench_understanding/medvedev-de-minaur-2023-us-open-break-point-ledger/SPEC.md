---
title: Medvedev-De Minaur Break-Point Ledger Spec Card
summary: Complete task, media, oracle-provenance, verifier, ablation, and formal-calibration record.
read_when: Reviewing, installing, or calibrating this task.
---

# Task Spec Card

## Submission status

The task implementation, provisional MCP-derived 16-event/112-shot oracle,
deterministic hierarchical verifier, canonical silent media, four Codex
calibration/ablation records, and one separately validated all-frame contact-sheet
diagnostic are prepared. In response to issue feedback, the official scorer now
matches exact break-point identities and awards field-level credit through a
summary/shot bottleneck. The retained full-media Codex submission scores `0.3305`
after 247 ATIF tool-call turns; the oracle scores `1.0` and an empty submission
scores `0.0`.

This is a transparent WIP, not a merge-readiness claim. The strong-model score is
above the preferred `<0.10` target, and the oracle-assisted fixed-prior diagnostic
scores `0.1833`. Two blind independent full-video annotations and adjudication are
pending. Claude Code is installed but unauthenticated, and no native Antigravity
Flash or Pro trajectory has passed the terminal validator; those attempts are
recorded as `NO_SCORE`, not numeric model results.

The exact baked media bytes are observed and independently bound by calibration.
The PR package intentionally preserves the already calibrated Dockerfile and image
identity; changing that build definition would create a different image and would
invalidate the retained image-bound runs until they were repeated.

## Structured task definition

```yaml
task: agentic_vbench_understanding/medvedev-de-minaur-2023-us-open-break-point-ledger
cognitive_level: understanding

modalities_required:
  video: "Required. The persistent scoreboard, serve attempts, ball contacts, player positions, and point outcomes identify and classify each break-point event."
  audio: "Not used. The canonical task artifact contains zero audio streams."

paths:
  input: /workspace/materials/match.mp4
  output: /workspace/output/solution.json

question: "Reconstruct every break-point opportunity and its complete ordered scored sequence of serves, successful rally strokes, winners, and terminal error attempts in the full match."
output_schema: "A JSON object containing break_points. Each chronological event contains set, medvedev_games, de_minaur_games, medvedev_points, de_minaur_points, server, opportunity, first_serve_in, outcome, serve_direction, rally_shots, terminal_player, terminal_stroke, terminal_court_position, terminal_result, terminal_error, and an ordered shots array whose entries each contain stroke and direction."

reference:
  events: 16
  shot_tokens: 112
  status: "Provisional MCP-derived oracle pending blind video-only annotation and adjudication."

evidence:
  - "First set, video t≈738–1512 s: De Minaur's three break-point opportunities in Medvedev service games."
  - "Second set, video t≈2260–2615 s: five repeated break points in De Minaur's 2-1 service game."
  - "Fourth set, video t≈6740–6855 s: two late break points in Medvedev's 4-1 service game."
  - "The complete 119-minute silent video is canonical evidence; the listed windows are review anchors, not an annotator packet or permission to skip the rest of the match."

ground_truth:
  source: "Official US Open match feed for match 1403, cross-checked against the pinned Match Charting Project point log."
  tier: "provisional MCP-derived; target human-verified tier is pending"
  verification: "The official feed reports Medvedev 5/10 and De Minaur 2/6 on break points, fixing 16 opportunities. Point identities and outcomes are cross-checked against the pinned MCP log. The 112 shot tokens and terminal fields are deterministically decoded from pinned MCP notation, but MCP is not either required blind annotator."
  human_verification: "Annotators A and B must independently scan the full canonical video without expected counts, MCP, oracle, or pre-cut windows; freeze and hash both ledgers; then form the candidate union and adjudicate every inclusion, field, and shot disagreement from video."

mcp:
  record: 20230904-M-US_Open-R16-Daniil_Medvedev-Alex_De_Minaur
  commit: 2c59eef194967e688b69e73df344184a06322cd8
  points_file: charting-m-points-2020s.csv
  points_file_sha256: 2cd43f73e0530a47ea4c02b99dae40177ca6d58a8ccf9189358eb05dffb4be9a
  workbook: MatchChart 0.3.2.xlsm
  workbook_sha256: 46e2349eee512296a86170449f6e463a6be91be9261a0c7b6b5d5a25c006729f
  point_ids: [19, 32, 42, 65, 66, 68, 70, 72, 108, 132, 144, 166, 172, 181, 187, 189]
  license: CC BY-NC-SA 4.0
  role: "Attributed third-party annotation and reproducible audit source; not machine truth and not a substitute for blind annotations A and B."

scorer:
  version: hierarchical-bottleneck-v1
  official_metric: "Chronologically align exact seven-field identities. For each aligned event, credit is min(nine-field summary accuracy, ordered shot-field accuracy). Reward is 2 * summed event credit / (n_predicted + n_reference)."
  bottleneck_behavior: "The weaker detail layer caps event credit. Correcting the non-bottleneck layer can leave reward unchanged until it crosses the other layer; this intentional plateau prevents one missing layer from being pooled against another."
  strict_diagnostic: "Exact ordered-event F1 is retained as a diagnostic and is not reward."
  malformed_and_extra_predictions: "False, duplicate, malformed, and extra events remain in the denominator. Extra object keys are diagnosed but do not alone reduce reward for otherwise correct required values."
  oracle_reward: 1.0
  null_reward: 0.0
  deterministic_tests: "32/32 judge tests plus calibration regrade tests passing"
  vlm_or_llm_judge: none

difficulty:
  measured_agent: "Codex CLI 0.149.1, gpt-5.6-sol, high reasoning, full canonical silent match."
  strong_agent_reward: 0.3305
  strict_exact_event_diagnostic: 0.0
  tool_call_turns: 247
  native_tool_operations: 233
  interpretation: "The run is long-horizon but does not pass the preferred reward threshold; this is a WIP calibration candidate."
  pending_models: "Claude Code Fable 5 and Opus 4.8; native Antigravity Gemini 3.5 Flash and Gemini 3.1 Pro. No pending model is assigned a score."

anti_shortcut:
  video_only: "Canonical input; the shipped task video is silent."
  audio_only: "Not applicable because the canonical artifact has no audio stream."
  no_media: {reward: 0.0, status: "strict-v3 generation record passed; agent abstained"}
  single_frame: {reward: 0.0, status: "strict-v3 generation record passed; agent abstained"}
  scoreboard_only: {reward: 0.1175, status: "clean v13; below 0.15"}
  score_result_fixed_prior: {reward: 0.1833, status: "deterministic non-agent oracle-assisted diagnostic; above 0.15 and openly unresolved"}
  frame_dump_observed_zero_calls: {reward: 0.0222, native_operations: 0, status: "strict-v2 post-run scope passed; backend tools=[] and tool_choice=none not proven"}

input:
  path: /workspace/materials/match.mp4
  url: https://github.com/inFaaa/agentic-vbench/releases/download/medvedev-de-minaur-2023-us-open-r4-media-v1/medvedev-de-minaur-2023-us-open-r4-720p.mp4
  source_sha256: d78c9246d5dd36b812c71b5f39bfa43ab86d1a7adf711fb7bbc6ff1d66d618b2
  source_bytes: 804641210
  sha256: d61bee17596a28dbc8f8b607e4fc0dd6542885dbe9cdad18e1953e89363b0860
  bytes: 685013111
  codec: h264
  resolution: 1280x720
  average_frame_rate: 30000/1001
  duration_seconds: 7152.578767
  length_min: 119.2
  decoded_frames: 214363
  audio_streams: 0
  construction: "Checksum-verify the hosted H.264/AAC source, copy only stream 0:v:0 without re-encoding, remove audio and source metadata, and expose the silent remux."
  observed_artifact_status: "The final SHA, bytes, stream probe, and decoded-frame count were observed in formal calibration and bound by retained manifests."
  docker_invariant_status: "The installed Dockerfile is preserved exactly as calibrated. The observed final SHA, byte length, stream probe, and frame count are bound by calibration manifests rather than claimed as checks from an unbuilt Dockerfile."

images:
  canonical_task_image_id: sha256:f592cda4dfc09ca25ae3a19d7e65d17248fb01059f061368eecf14ae1ae9cb28
  fixed_codex_image: avb-medvedev-codex@sha256:390fb56051fafb49b5b4b797cb15704469294f816255994e9ee0fd21fe2da06b
  fixed_codex_image_id: sha256:390fb56051fafb49b5b4b797cb15704469294f816255994e9ee0fd21fe2da06b
  fixed_codex_platform: linux/arm64

provenance:
  instruction_sha256: 2b025b557a17f2443e9b8f5951ee19562eee570038d092a7757b957555d1cd55
  current_judge_sha256: a47317a7d9b2095e8131ca4f93dbf500756d75ccaf3a7d47b1991ddfc60b93eb
  current_judge_tests_sha256: 35ed4790595822214ec4777606d5765dc47e3a6290bebf8a72a2090e73bea46e
  calibration_regrade_tests_sha256: 3f47680ac144d0aca1c3601335de3ab70c870e1e759bf91e2acdc1e594f1d1e2
  frozen_generation_judge_sha256: 3ece409c4c223c2bf2120fb1ef251d76c88bc6150fb59b4d0b6963bcf69c4b40
  frozen_generation_judge_tests_sha256: 6b1801277acdc2b73ee13c4a0f51b0ef90a2860edd43d834c872aec623cda5b4
  oracle_script_sha256: 75c03d3084ebc3670ffbf77ee2ca5b0a46f16f8a4feb6b1d834c80aaa3a4c5c5
  task_commit: "pending; retained validations bind frozen task-file and overlay checksums instead"
  oracle_details: calibration/ground-truth-provenance.md
  blind_annotation_protocol: calibration/independent-annotation.md
```

## Task contract

Each event identifies the set, player-specific game and point scores, server, and
opportunity number. It also reports nine point-summary fields and the complete
ordered sequence of serve and rally-shot `stroke`/`direction` pairs. The
instruction defines closed vocabularies and observable rules for serve direction,
court position, winners, forced and unforced errors, aces, unreturnable serves, and
unknown fallbacks.

The event count and shot count above describe the provisional reference, not the
blind annotation packet. Annotators must independently discover the candidate count
from a normal-speed full-video pass and revisit candidates or uncertain transitions
at 0.5x speed or slower.

## Official hierarchical verifier

The official score responds directly to the requested identity-first, field-level
hierarchy. Events are matched one to one and chronologically on all seven identity
fields. For each aligned event:

```text
summary_accuracy = correct required summary fields / 9
ordered_shot_accuracy = aligned stroke/direction atoms
                        / max(predicted atoms, reference atoms)
event_credit = min(summary_accuracy, ordered_shot_accuracy)
reward = 2 * sum(event_credit) / (n_predicted + n_reference)
```

The bottleneck requires both detail layers. It intentionally has plateaus: improving
the stronger layer does not change reward until it crosses the weaker layer. Shot
insertions, deletions, field errors, and ordering errors all lose credit. False,
duplicate, malformed, and extra events remain in the prediction denominator. Extra
object keys are diagnosed but do not alone erase correct required values.

Chronological exact-event F1 remains a strict diagnostic only. The full-media run
is `0.3305` official hierarchical F1 and `0.0` exact-event F1. The higher official
score is disclosed as a difficulty-gate failure, not hidden behind the strict
diagnostic.

- Oracle reward: `1.0`
- Empty or missing submission reward: `0.0`
- Deterministic judge tests: `32/32`
- Calibration artifact regrade tests: passing
- VLM/LLM judge: none

## Ground-truth and MCP provenance

The official US Open feed for match `1403` reports break-point conversions of
`5/10` for Daniil Medvedev and `2/6` for Alex De Minaur, fixing 16
opportunities before shot-level annotation. The current provisional point
identities, serve directions, rally lengths, terminal fields, and ordered shots are
decoded from Match Charting Project record
`20230904-M-US_Open-R16-Daniil_Medvedev-Alex_De_Minaur` at pinned commit
`2c59eef194967e688b69e73df344184a06322cd8`.

MCP is attributed under CC BY-NC-SA 4.0. Its point log and workbook hashes are
recorded above and in `calibration/ground-truth-provenance.md`, along with the raw
codes, decoding rules, first-fault audit, terminal classification rules, and all
16 point IDs. The codes expand deterministically to 112 scored tokens. MCP point
189's player-specific point score was corrected from an earlier inverted draft;
the current provisional oracle uses Medvedev `40`, De Minaur `AD`.

MCP is a third-party human annotation, not machine truth. It is neither blind
annotator A nor B and cannot establish the target `human-verified` tier. The
required video-only workflow is:

1. Give A and B byte-identical packets containing only the canonical silent video,
   instruction/schema, and blank ledger; do not disclose expected counts, MCP,
   oracle, pre-cut windows, or prior outputs.
2. Have each annotator independently scan the complete match, freeze the canonical
   ledger, and record its SHA before either ledger is revealed.
3. Construct the union of both frozen ledgers, retaining unmatched candidates.
4. Adjudicate inclusion and every scalar/shot disagreement from video, preserving
   A, B, the final value, and an observable rationale.
5. Freeze the video-only adjudicated ledger before comparing it with MCP or the
   provisional oracle. Any answer-key change requires verifier checks and complete
   calibration/ablation reruns.

## Formal Codex evidence

The first four measured rows use Codex CLI `0.149.1`, `gpt-5.6-sol`, high
reasoning, the same pinned Linux/arm64 image, and strict-v3 validation. The fifth
uses the same CLI, model, effort, image, and frozen task files through a narrower
strict-v2 post-run validator. Its claim is limited to zero model tool calls observed
in the preserved session; it does not prove backend `tools=[]` or
`tool_choice=none`.

| input | official reward | exact-event diagnostic | ATIF turns | native operations |
|---|---:|---:|---:|---:|
| full silent match | 0.3305 | 0.0 | 247 | 233 |
| no media | 0.0 | 0.0 | 3 | 3 |
| one representative frame | 0.0 | 0.0 | 7 | 9 |
| cleaned scoreboard graphics only | 0.1175 | 0.0 | 65 | 60 |
| 179 all-frame contact sheets; observed zero calls | 0.0222 | 0.0 | n/a | 0 |

The full-media run predicted 17 events, aligned all 16 reference identities, and
had zero exact events. The scoreboard-only run predicted all 16 identities and had
zero exact events. The contact-sheet diagnostic predicted 14 events, aligned one
identity, and had zero exact events. Full-run artifacts are retained under
`calibration/rollouts/`; ablation artifacts are under `calibration/ablations/`.

## Formal validation protocol

For the four conventional Codex records, strict-v3 validation binds the fixed image,
frozen instruction, generation-time exact judge/tests, oracle script, agent-visible
input manifest, overlay checksum, raw trajectory, submitted solution state, gateway
envelope, ATIF/native operation counts, and generation-time reward. The current
hierarchical verifier deterministically regrades the retained submitted solution;
`calibration/test_regrades.py` checks those new score artifacts. The old strict-v3
record is provenance evidence, not a claim that it validated the revised reward.
Provider or setup failures are not score rows.

The all-frame record uses a separate closed-world validator. It checks every
operation-bearing session layer, observes zero model calls, decodes the 179
preserved session images, and reruns the frozen judge. The original 191,878,896-byte
session remains local because it embeds images; the committed 158,978-byte
derivative replaces images, encrypted reasoning, and account rate-limit metadata
with deterministic byte/SHA records while preserving other timeline and operation
evidence.

Native Antigravity Flash and Pro attempts did not produce terminal-valid
trajectories. Compact privacy-safe failure provenance is committed under
`calibration/failures/`; complete local sanitized packages and raw runtime material
are not PR rollouts. Claude Code did not begin inference because its installed
client was unauthenticated. These are `NO_SCORE` records, not zero rewards.

## Anti-shortcut evidence and boundaries

The no-media, single-frame, and cleaned scoreboard-only runs change only the input
transform while retaining the frozen task and fixed Codex harness. The
score/result-plus-global-priors row is deterministic and non-agent: it is granted
all identities and outcomes, then applies one global guess to every
video-dependent field. It is not an upper bound on all famous-match or scoreboard
shortcuts.

The contact sheets contain every decoded source frame once in order, packed as 179
40×30 grids with 64×36 cells. Original sheets are 2560×1080; Codex preprocessing
stored 2048×864 session images. Although the validator confirms 179 ordered
payloads, a cryptographic source-sheet-to-processed-image mapping was not
reconstructed. Downsampling, preprocessing, and post-run tool-call observation all
require maintainer acceptance before this can be treated as an accepted
tools-disabled ablation.

The official results establish that no-media, single-frame, scoreboard-only, and
the observed-zero-call contact-sheet inputs remain below `0.15`. They do not prove
that all famous-match or non-video priors fail: the deliberately oracle-assisted
fixed-prior diagnostic scores `0.1833`, so shortcut hardening remains open.

## Pinned media, images, and build distinction

```text
hosted source:
  sha256 d78c9246d5dd36b812c71b5f39bfa43ab86d1a7adf711fb7bbc6ff1d66d618b2
  bytes  804641210

observed canonical silent artifact:
  sha256 d61bee17596a28dbc8f8b607e4fc0dd6542885dbe9cdad18e1953e89363b0860
  bytes  685013111
  H.264, 1280x720, 30000/1001 fps
  7152.578767 s, 214363 decoded frames, zero audio streams

existing calibrated image identities:
  canonical task image id:
    sha256:f592cda4dfc09ca25ae3a19d7e65d17248fb01059f061368eecf14ae1ae9cb28
  fixed Codex calibration image:
    avb-medvedev-codex@sha256:390fb56051fafb49b5b4b797cb15704469294f816255994e9ee0fd21fe2da06b
```

The installed Dockerfile is the definition used for the calibrated image and is
not replaced by this PR package. The observed final SHA, byte length, stream probe,
and frame count are independently bound in retained calibration manifests. Any
future Dockerfile change would create a different image configuration/history and
must be paired with a new image digest and fresh calibration; the existing image
identities above apply only to the preserved build.

No immutable task commit is recorded for the retained runs. Strict validation binds
the frozen task files and per-run overlay checksums instead.

## Current and generation-time task-file hashes

```text
2b025b557a17f2443e9b8f5951ee19562eee570038d092a7757b957555d1cd55  steps/solve/instruction.md
a47317a7d9b2095e8131ca4f93dbf500756d75ccaf3a7d47b1991ddfc60b93eb  steps/solve/tests/judge.py
35ed4790595822214ec4777606d5765dc47e3a6290bebf8a72a2090e73bea46e  steps/solve/tests/test_judge.py
3f47680ac144d0aca1c3601335de3ab70c870e1e759bf91e2acdc1e594f1d1e2  calibration/test_regrades.py
75c03d3084ebc3670ffbf77ee2ca5b0a46f16f8a4feb6b1d834c80aaa3a4c5c5  steps/solve/solution/solve.sh
5cf23c869961b4e6e5162633be034268a105ac77775dd297f8f40674131897b2  environment/Dockerfile
```

The strict-v3 generation records bind the superseded exact-judge hashes
`3ece409c...` and `6b180127...`. They are preserved inside each validation record
and are not relabeled as current source hashes.

## Open acceptance items

- Harden and rerun after the current hierarchical strong-model score of `0.3305`;
  the WIP does not meet the preferred `<0.10` difficulty gate.
- Address or explicitly accept the oracle-assisted fixed-prior diagnostic at
  `0.1833`, above the usual `0.15` ablation ceiling.
- Complete and commit the two blind independent full-video ledgers, their packet
  manifests and attestations, candidate union, adjudication ledger, hashes, and
  sign-off before claiming a human-verified oracle.
- Preserve the calibrated Dockerfile. If a later change hardens its post-remux
  assertions, record the new image digest and rerun every image-bound calibration.
- Complete authenticated native Claude Code Fable 5 and Opus 4.8 runs.
- Complete terminal-valid, independently validated native Antigravity CLI `1.1.22`
  Gemini 3.5 Flash and Gemini 3.1 Pro runs. No score may be entered for setup,
  policy, authentication, quota, or incomplete-archive failures.
- Obtain maintainer approval for the all-frame observed-zero-call protocol or
  replace it with an auditable backend-disabled-tools run. The current evidence
  explicitly does not prove `tools=[]` or `tool_choice=none`.
- Add the immutable submitted task commit to future validation records.
