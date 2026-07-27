# Experiment Audit Report

**Date**: 2026-07-27
**Auditor**: External reviewer backend (gpt-5.5), xhigh reasoning, read-only
**Project**: europarl-2026-single-market-speaker-turn-ledger

## Overall Verdict: WARN

## Integrity Status: warn

## Checks

### A. Ground Truth Provenance: PASS

The task now records official source URLs, retrieval date, hashes, page/record counts, player metadata, HLS hash, selection rule, anonymization seed, published artifact hashes, and expected GT hash in `calibration/source_provenance.json` (`calibration/source_provenance.json:2`, `calibration/source_provenance.json:6`, `calibration/source_provenance.json:12`, `calibration/source_provenance.json:17`, `calibration/source_provenance.json:24`, `calibration/source_provenance.json:33`, `calibration/source_provenance.json:41`, `calibration/source_provenance.json:47`). `calibration/build_ground_truth.py` parses the 3-page PDF, parses/cross-checks 170 HTML records, applies the fixed non-chair >=30s rule, applies seed 20260715, and emits the GT SHA-256 (`calibration/build_ground_truth.py:44`, `calibration/build_ground_truth.py:47`, `calibration/build_ground_truth.py:86`, `calibration/build_ground_truth.py:108`, `calibration/build_ground_truth.py:116`, `calibration/build_ground_truth.py:119`, `calibration/build_ground_truth.py:126`, `calibration/build_ground_truth.py:163`). The current `steps/solve/tests/gt.json` hash matches the provenance manifest (`calibration/source_provenance.json:41`), and `SPEC.md`/`scores.md` link the provenance/constructor artifacts (`SPEC.md:29`, `calibration/scores.md:6`, `calibration/scores.md:8`). No proxy/model-generated GT pattern remains.

### B. Construct and Measurement Validity: WARN

The claimed construct is reconstruction of every substantive non-chair speaker turn of at least 30 seconds with anonymous identity and audible floor-audio boundaries (`SPEC.md:18`, `steps/solve/instruction.md:11`, `steps/solve/instruction.md:16`, `steps/solve/instruction.md:20`). The operational metric requires exact `speaker_id` and both boundaries within 4 seconds (`SPEC.md:31`, `SPEC.md:32`; `steps/solve/tests/judge.py:86`, `steps/solve/tests/judge.py:92`). This matches the task definition, and media/audio alignment evidence exists (`calibration/media_alignment.json:41`, `calibration/audio_alignment.json:2`, `calibration/audio_alignment.json:6`). Warning: the 4-second boundary tolerance is justified mainly by scripted shortcut diagnostics (`calibration/scripted_baselines.md:12`, `calibration/scripted_baselines.md:21`), not by independent human agreement or a preregistered measurement-validity study.

### C. Data and Target-Event Support: WARN

The single benchmark instance covers a 7,662-second, 1080p source video (`environment/Dockerfile:25`, `environment/Dockerfile:27`) with 86 turns and 79 unique speakers in the shipped target (`steps/solve/tests/gt.json:2`, `steps/solve/tests/gt.json:514`, `steps/solve/tests/gt.json:517`). Observability evidence reports candidate frames for all 79 speakers and 79/79 manual identity matches (`calibration/observability_79.md:15`, `calibration/observability_79.md:18`; `calibration/observability_79.json:2`, `calibration/observability_79.json:1038`). Warning: there is no development/calibration/untouched-confirmation split or sample-size/progression requirement in the listed artifacts, so claims should remain scoped to this one benchmark item.

### D. Model/Intervention Role Fitness: PASS

Roles are appropriately separated: task agents are generators/policies producing `solution.json` (`steps/solve/instruction.md:23`), `judge.py` is a deterministic verifier (`steps/solve/tests/judge.py:116`, `steps/solve/tests/judge.py:158`), and `oracle.json` is an oracle/ceiling copied only by the supplied solution script (`steps/solve/solution/solve.sh:5`). Calibration trajectories exercise three model families through Copilot CLI and report harness/model identities without relabeling (`calibration/scores.md:10`, `calibration/scores.md:21`). No LLM judge or simulator is used on the critical scoring path.

### E. Baseline Independence: PASS

The primary comparisons include oracle, empty/null, three full-agent runs, and degraded-input ablations (`calibration/scores.md:15`, `calibration/scores.md:21`, `calibration/scores.md:23`, `calibration/scores.md:31`). Scripted video-only diagnostics are explicitly labeled deterministic diagnostics, not substitutes for strong-model ablations (`calibration/scripted_baselines.md:1`, `calibration/scripted_baselines.md:4`). The raw rollout scan found no references to `gt.json`, `oracle.json`, `judge.py`, `/tests`, or reward files in the three listed calibration trajectories; the task also disables internet in configuration (`task.toml:17`), and the prompt forbids public lookup (`steps/solve/instruction.md:45`, `steps/solve/instruction.md:46`).

### F. Identification and Assay Sensitivity: PASS

Positive and negative controls exist: oracle and null anchors are reported (`calibration/scores.md:17`, `calibration/scores.md:18`), and the verifier yields exact oracle reward 1.0 and empty reward 0.0 (`steps/solve/tests/judge.py:117`, `steps/solve/tests/judge.py:133`, `steps/solve/tests/judge.py:158`). Degraded-input controls include no media, single frame, video only, audio only, and frame-dump/no-tools runs (`calibration/scores.md:27`, `calibration/scores.md:31`). The video-only scripted diagnostic drops sharply at the final 4-second tolerance, supporting assay sensitivity to boundary precision (`calibration/scripted_baselines.md:14`, `calibration/scripted_baselines.md:17`, `calibration/scripted_baselines.md:19`).

### G. Evaluator Qualification: WARN

The primary evaluator is deterministic code rather than a model/human judge, with schema checks, valid speaker checks, monotonic one-to-one matching, and precision/recall/F1 output (`steps/solve/tests/judge.py:52`, `steps/solve/tests/judge.py:57`, `steps/solve/tests/judge.py:96`, `steps/solve/tests/judge.py:133`). Warning: the supporting identity observability audit uses one manual reviewer (`calibration/observability_79.json:6`) and private contact sheets not duplicated in git (`calibration/observability_79.md:29`, `calibration/observability_79.md:31`), so human agreement, blinding, and adjudication are not inspectable.

### H. Information and Statistical Adequacy: WARN

The scored unit is a turn, with 86 ground-truth events and 79 speakers (`steps/solve/tests/gt.json:2`, `steps/solve/tests/gt.json:514`; `calibration/observability_79.json:2`). The verifier reports raw counts, precision, recall, and F1 (`steps/solve/tests/judge.py:126`, `steps/solve/tests/judge.py:133`). Warning: calibration uses one trajectory per listed model and one task video (`calibration/scores.md:19`, `calibration/scores.md:21`), with no confidence intervals, seed/context variability analysis, multiplicity handling, or sample-size justification. Model-difficulty claims should not be generalized beyond these observed runs.

### I. Leakage and Fresh Evidence: PASS

The shipped materials expose only `debate.mp4`, `roster.json`, and roster portraits to the solver (`steps/solve/workdir/setup.sh:4`, `steps/solve/workdir/setup.sh:7`; `steps/solve/instruction.md:3`, `steps/solve/instruction.md:7`). The scorer loads ground truth from the tests directory only at evaluation time (`steps/solve/tests/judge.py:14`, `steps/solve/tests/judge.py:15`), and calibration raw trajectories do not reference verifier/ground-truth/oracle paths. The Dockerfile pins downloaded media/roster hashes (`environment/Dockerfile:7`, `environment/Dockerfile:11`) and marks a canary (`environment/Dockerfile:33`).

### J. Result and Computation Integrity: PASS

The verifier computes raw monotonic one-to-one F1 without self-normalization (`steps/solve/tests/judge.py:117`, `steps/solve/tests/judge.py:133`) and writes both JSON and text rewards (`steps/solve/tests/judge.py:157`, `steps/solve/tests/judge.py:161`). `calibration/results.json` now records the exact verifier hash/metric, oracle and null anchors, each full-agent run's score/counts/tool calls/status/trajectory hash, each anti-shortcut result, the scripted baseline, and complete checker status (`calibration/results.json:2`, `calibration/results.json:7`, `calibration/results.json:8`, `calibration/results.json:21`, `calibration/results.json:22`, `calibration/results.json:73`, `calibration/results.json:75`, `calibration/results.json:120`, `calibration/results.json:121`, `calibration/results.json:132`). The manifest hashes match the current verifier and three raw trajectories, and `calibration/scores.md` links `results.json` as the exact count/status source (`calibration/scores.md:6`, `calibration/scores.md:8`). No phantom-result, score-normalization, missing-result, or dead-code pattern was found.

### K. Scope and Claim Alignment: WARN

The claims are mostly scoped to one task, one source video, 79 roster speakers, and three calibrated full-agent model runs (`SPEC.md:10`, `SPEC.md:18`, `SPEC.md:39`; `calibration/scores.md:19`, `calibration/scores.md:21`). Warning: words like "strong_agent_reward: 0.0" and "hard" are supported only by single raw trajectories per model family and should be read as benchmark-calibration evidence, not a robust/general model capability estimate (`SPEC.md:36`, `SPEC.md:39`; `calibration/scores.md:10`, `calibration/scores.md:13`).

### L. Outcome Classification: mixed

The task artifact, ground-truth construction, and deterministic scoring path are supported: provenance and constructor artifacts now reproduce and hash-bind the GT (`calibration/source_provenance.json:30`, `calibration/source_provenance.json:42`; `calibration/build_ground_truth.py:153`, `calibration/build_ground_truth.py:164`), result manifests hash-bind the verifier and raw trajectories (`calibration/results.json:4`, `calibration/results.json:37`, `calibration/results.json:54`, `calibration/results.json:71`), and the metric is directly wired into `test.sh` (`steps/solve/tests/test.sh:10`, `steps/solve/tests/test.sh:13`). Remaining caveats are scope/statistical/manual-review qualifications, not provenance or result-integrity failures. No hard evidence of fake ground truth, self-normalization, circular baselines, phantom results, or verifier leakage was found.

## Action Items

- Document the boundary-tolerance rationale and any human/manual identity review protocol, including reviewer count, blinding/adjudication, and reproducible contact-sheet generation.
- Narrow any difficulty/generalization wording to "observed on these single calibration trajectories" unless more seeds/tasks/models are added.

## Claim Impact

- Claim 1, official-machine-truth ledger: supported for the packaged task because provenance, constructor, and GT hash are now recorded and linked.
- Claim 2, deterministic scorer validity for this task: supported.
- Claim 3, modality/shortcut resistance: needs qualifier; controls support the claim, but evidence is single-task.
- Claim 4, strong-agent difficulty scores: needs qualifier only for statistical/generalization scope; exact run scores/counts/statuses and trajectory hashes are now packaged.
