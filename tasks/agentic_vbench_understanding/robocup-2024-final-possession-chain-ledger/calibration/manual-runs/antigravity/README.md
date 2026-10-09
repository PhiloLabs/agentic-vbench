---
title: Antigravity manual run
summary: OAuth preparation and one-command Harbor execution for Antigravity CLI.
read_when: Running RoboCup with the Antigravity harness and a Gemini 3 model.
---

# Antigravity CLI

For a self-contained brief that can be handed directly to Antigravity App, use
`APP_HANDOFF.md`. It separates OAuth/model research from the single clean benchmark
attempt and defines the evidence required for review.

Harbor's Antigravity adapter uses a Google OAuth token, not a Gemini API key. Create
the token once in a throwaway login container:

```bash
export AGY_AUTH_JSON_PATH="$HOME/.gemini/antigravity-cli/robocup-harbor-token"
harbor agy login --output "$AGY_AUTH_JSON_PATH"
chmod 600 "$AGY_AUTH_JSON_PATH"
```

Then select one README-approved model and run:

```bash
export ANTIGRAVITY_MODEL=google/gemini-3.1-pro

bash tasks/agentic_vbench_understanding/robocup-2024-final-possession-chain-ledger/\
calibration/manual-runs/antigravity/run.sh
```

`google/gemini-3.5-flash` may replace Gemini 3.1 Pro. Confirm the exact model ID is
available to the signed-in Antigravity account before starting. Do not change models
or rerun after seeing the score.

The build-time preflight installed Antigravity CLI `1.1.20` on 2026-08-25. The
installer is not version-addressable, so the wrapper records the actual installed
version from each trial rather than claiming a pin it cannot enforce.

The wrapper uploads the token through Harbor's credential path, runs one attempt
with `reasoning_effort=high`, and retains the Antigravity native trajectory plus
Harbor ATIF output. The adapter removes its container-side OAuth token after the
run. Delete the host token when calibration is complete:

```bash
rm -f -- "$AGY_AUTH_JSON_PATH"
unset AGY_AUTH_JSON_PATH
```

Record the installed `agy` version from the trial, exact model ID, exact reward/IoU,
ATIF tool-call turns, trajectory SHA256, image ID, task commit, and task
checksum in `calibration/scores.md`.
