# Raw calibration trajectories

Keep one complete raw trajectory per required agent and degraded-input run. Each
trajectory must include all tool calls and the final answer; summaries are not
acceptable calibration evidence.

The pre-inferential-card trajectories are superseded and are not calibration
evidence for the frozen task. This directory stores compact audit JSONL, exact
solutions when an agent wrote one, verifier rewards, proxy audits, summaries and
manifests for the three full agents and five degraded-input runs.

Lossless raw trajectories and proxy logs are pinned at immutable Hugging Face
revision `ea0cfe009016f3060f1d9a10c6cef55eae86bec8` under
`calibration-inferential-final-v3/`; direct links are in `../scores.md`.

The upstream guide asks for raw trajectories inside the PR. Keeping the lossless
files remote avoids adding hundreds of megabytes to git while preserving immutable
bytes and SHA256 manifests; this placement is an explicit maintainer waiver
request, not a claim of literal native compliance.
