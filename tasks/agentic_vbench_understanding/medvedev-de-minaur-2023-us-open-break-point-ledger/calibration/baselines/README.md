# Deterministic baselines

These files are scorer checks or explicitly oracle-assisted diagnostics. They are
not model trajectories.

## Anchors

| baseline | reward | expected |
|---|---:|---:|
| oracle | 1.0000 | 1.0000 |
| empty submission | 0.0000 | 0.0000 |

The anchor solutions and current `hierarchical-bottleneck-v1` reward files are in
`anchors/`. The oracle solution is generated from `steps/solve/solution/solve.sh`;
the verifier-side answer remains absent from the agent environment.

## Score/result fixed prior

`score-result-prior-v4-exact/solution.json` deliberately receives every exact
seven-field break-point identity and every `outcome` from the oracle. It then uses
one fixed global modal guess for each remaining video-dependent field and a minimal
shot sequence. This construction asks how far a highly privileged score/result
prior can travel without reconstructing each rally.

| component | result |
|---|---:|
| predicted events | 16 |
| ordered identity matches | 16 |
| summary fields correct | 75/144 |
| ordered shot fields correct | 23/224 reference atoms |
| hierarchical reward | **0.1833** |
| exact-event diagnostic | 0.0 |

The current score exceeds `0.15`. This is an open WIP shortcut-risk signal and must
not be reported as a passing ablation. It is also not a no-media upper bound: the
probe is granted oracle identities and outcomes that a real no-media agent does not
receive. The measured no-media agent abstained and scored `0.0`.

The neighboring `reward.json` is the frozen generation-time exact-judge record.
`hierarchical-verifier-details.json` is authoritative for the current metric. Both
are retained to make the scoring migration auditable.
