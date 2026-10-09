# Calibration rollouts

Only compact metadata lives in the repo:

- `manifest.json` — every raw trajectory's filename, SHA-256, byte length, run
  identity, and status (pre-contract evidence, interrupted diagnostic, or
  branch-history only).
- `<run>.solution.json` and `<run>.reward.json` — the submitted ledger and the verifier
  output, so each recorded score can be reproduced with `steps/solve/tests/judge.py`.

The raw trajectories themselves (about 200 MB) are not committed. Copies are kept
outside git and are not yet published to Git LFS or an immutable external revision.
When they are, add the revision URL to `manifest.json`. Verify any copy against the
recorded SHA-256 and byte length before trusting it.

Earlier commits on this branch (`157e7b4`, `4f03679`) contain the raw blobs. Merge with
a squash or rewritten history so they do not enter `main`.
