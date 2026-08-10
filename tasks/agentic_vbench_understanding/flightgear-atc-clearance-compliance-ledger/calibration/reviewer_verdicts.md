# Independent reviewer verdicts

Three independent reviewer tracks were run repeatedly during hardening:

1. code and scorer correctness;
2. media, ground-truth, and calibration evidence integrity;
3. AgenticVBench PR readiness.

Early reviews blocked on real defects including frozen visible instruments,
pre-speech response, invalid recovery evidence, scorer edge cases, stale
summaries/checkpoints, mutable ASR assets, missing peak frames, and generator
test divergence. Those findings were fixed and re-reviewed.

## Final verdicts

| Reviewer track | Verdict | Remaining concerns |
|---|---|---|
| code/scorer | PASS WITH GOVERNANCE DEVIATIONS | none in implementation |
| evidence integrity | PASS WITH GOVERNANCE DEVIATIONS | none in evidence package |
| PR readiness | PASS WITH GOVERNANCE DEVIATIONS | none in package structure |

Final verification included:

- 17 verifier/adversarial tests;
- 16 generator/controller/derivation tests using the shipped judge;
- official understanding checker;
- Harbor oracle 1.0;
- immutable media and ASR checksum build;
- 65-event, 300-frame observability evidence;
- current durable checkpoint and calibration-summary hash checks.

## Governance deviations

The reviewers consistently identified two non-hidden sign-offs outside code
correctness:

1. Issue #95 has no explicit maintainer approval yet for simulator-rendered,
   externally controlled FlightGear media.
2. The contributor explicitly requested GitHub Copilot model-family calibration
   instead of vendor-native Codex CLI, Claude Code, and Antigravity.

The package is ready for contributor review, but PR submission remains gated on
that review.
