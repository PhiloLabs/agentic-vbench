# Calibration scores

## Official scoring policy

The official verifier is `hierarchical-bottleneck-v1`. It first aligns submitted
events one to one and chronologically on the seven exact identity fields: set, both
game scores, both point scores, server, and opportunity number. For each aligned
event `e`, it then computes:

```text
summary_accuracy_e = correct required summary fields / 9
ordered_shot_accuracy_e = aligned shot-field atoms
                          / max(predicted shot-field atoms,
                                reference shot-field atoms)
event_credit_e = min(summary_accuracy_e, ordered_shot_accuracy_e)
reward = 2 * sum(event_credit_e) / (n_predicted + n_reference)
```

Shot alignment is order preserving and gives one atom each to `stroke` and
`direction`. Insertions increase the predicted denominator; deletions lose
reference matches; order changes lose aligned atoms. False, duplicate, malformed,
and extra events remain in `n_predicted`, so they reduce precision. Missing events
reduce recall. A submission with only identities, only summaries, or only shots
receives zero event credit.

The `min` is an intentional conjunctive bottleneck: an event can receive no more
credit than its weaker summary or shot-sequence layer. Consequently, improving a
non-bottleneck layer does not increase reward until it crosses the other layer.
The metric is therefore monotone but has documented plateaus; it does not claim
that every newly correct field immediately changes the score. This avoids both a
scoreboard-only summary and an ungrounded shot list masking a missing required
layer, while still awarding partial field-level credit within both layers.

The verifier also emits chronological exact-event F1 as a strict diagnostic. It is
not the reward. Input is bounded at 256 events, 512 shots per event, and 4096 total
submitted shots; over-limit submissions fail closed to zero through the CLI.

## Measured performance

All numeric rows below are deterministic regrades of retained submitted solutions
with the current verifier. The model trajectories were produced with the same
frozen instruction, oracle, fixed image, and canonical silent media. Their original
strict-v3 validation records bind the generation-time files and frozen exact
reward, but do not claim to validate this later reviewer-requested metric revision.
The current `*.hierarchical-verifier-details.json` files are the authoritative score
records and are rechecked by `calibration/test_regrades.py`.

| harness | harness version | model | reasoning | input | reward | predicted | tool-call turns | runtime | trajectory |
|---|---|---|---|---|---:|---:|---:|---:|---|
| Codex CLI | 0.149.1 | GPT-5.6 Sol | high | full silent match | **0.3305** | 17 | 247 | 61m31s | `rollouts/codex-gpt-5.6-sol-high-v10-full-media.raw.txt` |
| Codex CLI | 0.149.1 | GPT-5.6 Sol | high | no media | 0.0000 | 0 | 3 | 4m18s | `ablations/codex-gpt-5.6-sol-high-v11-no-media.raw.txt` |
| Codex CLI | 0.149.1 | GPT-5.6 Sol | high | one representative frame | 0.0000 | 0 | 7 | 4m57s | `ablations/codex-gpt-5.6-sol-high-v11-single-frame.raw.txt` |
| Codex CLI | 0.149.1 | GPT-5.6 Sol | high | scoreboard graphics only | 0.1175 | 16 | 65 | 41m54s | `ablations/codex-gpt-5.6-sol-high-v13-scoreboard-only.raw.txt` |
| Codex CLI | 0.149.1 | GPT-5.6 Sol | high | all-frame contact sheets; zero calls observed | 0.0222 | 14 | n/a | 12m47s | `ablations/codex-gpt-5.6-sol-high-v1-frame-dump-observed-zero-call.raw.txt` |

The full run aligned all 16 reference identities from 17 predictions. It recovered
79/144 summary atoms and 136 ordered shot-field atoms, but no fully exact event. Its
hierarchical true-positive credit is `5.4539`, giving precision `0.3208`, recall
`0.3409`, and F1 `0.3305`. This is a real long-horizon attempt, but it exceeds the
benchmark's preferred `<0.10` difficulty gate. This PR is therefore a transparent
WIP calibration candidate, not a conditions-satisfied or merge-ready claim.

## Anchors and deterministic baseline

| check | reward | status | artifact |
|---|---:|---|---|
| oracle | 1.0000 | required anchor passes | `baselines/anchors/oracle/reward.json` |
| empty | 0.0000 | required anchor passes | `baselines/anchors/empty/reward.json` |
| identity/outcome-granted fixed prior | 0.1833 | diagnostic; exceeds 0.15 | `baselines/score-result-prior-v4-exact/hierarchical-verifier-details.json` |

The fixed prior is not an agent run. It is deliberately granted every reference
identity and outcome, then repeats global modal guesses for video-dependent fields.
Its `0.1833` score is disclosed as an open shortcut-risk signal; it is neither a
passing ablation nor an estimate of what no-media agents can obtain.

## Frozen generation records

The retained `.reward.json` and `.validation.json` files beside each trajectory are
unaltered generation-era records. They report exact-event reward `0.0` and the
retired product diagnostic (`0.2075` for full media). They remain useful for
provenance because they bind the raw trajectory, image, task overlay, submitted
solution, tool-call counts, and old judge hash. The current score is always the
separate `*.hierarchical-verifier-details.json` file.

```text
fixed image: avb-medvedev-codex@sha256:390fb56051fafb49b5b4b797cb15704469294f816255994e9ee0fd21fe2da06b
canonical silent media sha256: d61bee8583c68f956bc0ffc5b87fd967468546b0b8514943842b9ffb79a0b860
canonical media bytes: 685013111
reference events: 16
reference shot tokens: 112
```

## Cross-harness status

Claude Code Fable 5/Opus 4.8 and native Antigravity Flash/Pro do not have valid
terminal trajectories. They are recorded as `NO_SCORE`, never as zero-scoring model
runs, in `calibration/failures/`. The WIP remains incomplete until authenticated,
terminal-valid trajectories are available or maintainers explicitly accept the
current scope.
