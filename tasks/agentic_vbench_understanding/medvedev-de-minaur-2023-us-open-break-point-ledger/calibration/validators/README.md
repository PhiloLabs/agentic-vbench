# Calibration validators

`frozen-exact-v1/` contains the portable validators and mutation tests used to seal
the retained Codex trajectories when the generation-time official reward was exact
ordered-event F1. They bind the image, task overlay, raw trajectory, submitted
solution, operation counts, gateway envelope, and original reward artifacts.

The reviewer-requested `hierarchical-bottleneck-v1` scorer was adopted after those
runs. The frozen validators are retained unchanged as provenance and must not be
described as validation of the new reward. Current submitted solutions are regraded
by `../test_regrades.py`, while the official scorer itself is covered by
`steps/solve/tests/test_judge.py`.

Do not update the frozen validator pins to make an old validation record appear to
have been produced by the new scorer. A future end-to-end run should create a new
validator revision and new trajectory instead.
