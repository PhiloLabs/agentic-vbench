# Experiment Audit Report

**Date**: 2026-07-28
**Auditor**: External Codex reviewer, GPT-5.5 xhigh, read-only artifact review
**Project**: europarl-2026-single-market-speaker-turn-ledger

## Overall Verdict: WARN

## Integrity Status: warn

The evaluation package is technically transparent and reproducible enough for a warning, not a fraud fail. The key caveat is claim/policy alignment: the upstream strong-agent requirement is singular/GPT-first in the current checker, and GPT-5.6 Sol passes, but Claude Opus 5 is above the nominal `< 0.10` README threshold. The Copilot harness substitution and Hugging Face hosting substitution are explicit maintainer-policy waivers rather than hidden technical integrity failures.

## Checks

### A. Ground Truth Provenance: PASS

Ground truth is constructed from official European Parliament sources, not from model predictions: the builder parses a 3-page PDF and 170 HTML records, cross-checks name/role/duration/start/end equality, applies a fixed non-chair and duration rule, and writes 86 selected turns (`calibration/build_ground_truth.py:47`, `calibration/build_ground_truth.py:77`, `calibration/build_ground_truth.py:89`, `calibration/build_ground_truth.py:115`, `calibration/build_ground_truth.py:123`, `calibration/build_ground_truth.py:139`). Source hashes and counts are recorded (`calibration/source_provenance.json:4`, `calibration/source_provenance.json:10`, `calibration/source_provenance.json:41`, `calibration/source_provenance.json:42`). The model-authored semantic cards are explicitly labeled auxiliary materials, not official labels (`SPEC.md:29`, `calibration/semantic_card_qualification.json:126`).

### B. Construct and Measurement Validity: WARN

The construct is multimodal long-horizon understanding: identity, language, semantic-card match, and boundaries (`SPEC.md:15`, `SPEC.md:18`). The verifier requires exact speaker/language/card and boundary tolerance, then computes monotonic event F1 (`steps/solve/tests/judge.py:151`, `steps/solve/tests/judge.py:163`, `steps/solve/tests/judge.py:183`). Validity evidence includes semantic ceiling 86/86 by two model families and lexical shortcut preflight below threshold (`calibration/card_semantic_ceiling.json:20`, `calibration/card_semantic_ceiling.json:33`, `calibration/semantic_card_qualification.json:94`). Warning: language observability is 82/86, not perfect (`calibration/language_observability.json:5`), and the semantic-card channel is model-authored even though audited.

### C. Data and Target-Event Support: PASS

The task has enough concrete target events for the claimed benchmark instance: 86 scored turns, 79 speakers, 742 roster entries, 21 languages, 86 semantic cards (`calibration/results.json:45`, `calibration/results.json:51`). Boundary/media support is measured on the 7,662 s artifact with ten speech-export checks and a 3.5 s derived tolerance (`calibration/media_alignment.json:9`, `calibration/media_alignment.json:19`, `calibration/media_alignment.json:30`). The data support is instance-specific, not broad population evidence.

### D. Model/Intervention Role Fitness: PASS

System roles are separated: official sources are oracle/ground truth, deterministic scripts build and score, SpeechBrain/Whisper/YuNet/SFace are diagnostic baselines, and LLMs are task solvers or semantic-card material auditors/ceiling controls. The scorer is deterministic and not an LLM judge (`steps/solve/tests/judge.py:183`, `steps/solve/tests/judge.py:235`). The card-authoring model role is disclosed and cross-checked (`calibration/semantic_card_qualification.json:51`, `calibration/semantic_card_qualification.json:63`). Fixed-output replay is not used as evidence for an intervention claim; raw trajectories are retained (`calibration/rollouts/README.md:3`, `calibration/rollouts/README.md:12`).

### E. Baseline Independence: WARN

Simple baselines and anti-shortcut controls exist: empty 0.0, scripted semantic 0.0625, full-agent runs, and five degraded-input runs at 0.0 (`calibration/results.json:61`, `calibration/results.json:71`, `calibration/results.json:158`). The semantic ceiling is correctly framed as a ceiling/control, not a fair solver comparator (`calibration/card_semantic_ceiling.json:2`, `calibration/card_semantic_ceiling.json:45`). Warning: the scripted perception/card baseline is partly used during design hardening and should remain a diagnostic, not confirmation (`calibration/semantic_card_qualification.json:9`, `calibration/semantic_card_qualification.json:94`).

### F. Identification and Assay Sensitivity: PASS

Positive, negative, and discriminator controls are present: oracle 1.0 and empty 0.0 (`calibration/results.json:61`), five degraded-input ablations all 0.0 (`calibration/scores.md:40`), semantic ceiling 86/86 (`calibration/card_semantic_ceiling.json:26`, `calibration/card_semantic_ceiling.json:37`), and frame-dump readability/identity controls showing the no-tool bundle is readable but open-set identity search fails without agency (`calibration/frame_dump_observability.json:19`, `calibration/frame_dump_observability.json:58`, `calibration/frame_dump_observability.json:77`).

### G. Evaluator Qualification: PASS

The primary evaluator is deterministic stdlib scoring, not a human/LLM judge (`steps/solve/tests/judge.py:183`). LLM qualification applies only to semantic-card material; the staged qualification report records the failed first audit, correction recheck, final advisory recheck, and exact hashes (`calibration/semantic_card_qualification.json:55`). Public per-card source evidence is staged in `calibration/semantic_card_sources.json`. Those audits qualify input material, not scoring.

### H. Information and Statistical Adequacy: WARN

For the single benchmark task, the unit is an event/turn and the package reports raw counts and exact scores (`steps/solve/tests/judge.py:195`, `calibration/results.json:107`). However, there are no uncertainty intervals or formal power calculations for claims about robustness/generalization. The README itself specifies task-level gates, not statistical inference (`README.md:32`, `README.md:52`). Treat this as benchmark-qualification evidence, not a population-level scientific result.

### I. Leakage and Fresh Evidence: PASS

Agent instructions forbid internet/public lookup and hidden prior knowledge (`steps/solve/instruction.md:82`). The task config disables internet (`task.toml:17`). The staged harness-isolation report records the unique internal network, host firewall, auth-sealing proxy, immutable image assertion, and blocked host/public-oracle probes (`calibration/harness_isolation.json:44`, `calibration/harness_isolation.json:64`).

### J. Result and Computation Integrity: PASS

No self-normalization was found: reward is standard F1 from true positives, predicted count, and ground-truth count (`steps/solve/tests/judge.py:183`, `steps/solve/tests/judge.py:188`, `steps/solve/tests/judge.py:190`). Reported rewards exist and match the result tracker: GPT 0.023392, Opus 0.116279, Gemini 0.0 (`calibration/results.json:107`, `calibration/results.json:141`, `calibration/scores.md:22`). Oracle and empty anchors are present (`calibration/results.json:61`). The immutable raw package API lists the referenced raw trajectories and reward/proxy files at revision `ea0cfe009016f3060f1d9a10c6cef55eae86bec8`.

### K. Scope and Claim Alignment: WARN

The technical claims are mostly aligned with one frozen task. The explicit weak point is policy/claim wording: README says a strong current agent must be `< 0.10` and calibration should cover Antigravity/Codex/Claude Code (`README.md:32`, `README.md:34`), while this package uses GitHub Copilot CLI for all three and reports Opus at 0.116279 (`calibration/scores.md:14`, `calibration/scores.md:23`). The staged result manifest explicitly lists the harness, source-hosting, and remote-raw placement waiver requests (`calibration/results.json:45`). This is a transparent warning, not hidden fraud.

### L. Outcome Classification: mixed

Supported: official ground truth, deterministic scoring, result existence, leakage firewall, and GPT-first checker pass. Needs qualifier: general "all strong agents < 0.10" is not supported because Opus is 0.116279. Policy-dependent: the three explicit substitutions in `calibration/results.json` require maintainer waiver acceptance.

## Action Items

1. Narrow calibration wording to "GPT-5.6 Sol passes the singular upstream checker; Opus is a disclosed above-threshold warning."
2. Keep semantic ceiling and scripted baselines labeled as controls/diagnostics, never fair solver comparators.
3. Obtain explicit maintainer acceptance for Copilot harness substitution and Hugging Face hosting, or rerun in the native harness/source policy requested by README.

## Claim Impact

- Official ground truth and deterministic verifier: supported.
- Hard GPT-first calibration: supported.
- All evaluated strong agents below `< 0.10`: unsupported; requires qualifier.
- Anti-shortcut ablation gates: supported for measured GPT-5.6 Sol degraded-input runs.
- Harness/source policy compliance: needs explicit waiver.
