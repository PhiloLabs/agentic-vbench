---
title: RoboCup manual Claude and Antigravity runs
summary: Reproducible Harbor wrappers for the two user-operated calibration agents.
read_when: Running the final Claude Code or Antigravity calibration manually.
---

# Manual calibration runs

These wrappers run the unchanged checked-in instruction and verifier in Harbor
0.20 Docker isolation. They create a temporary task copy using the already-downloaded
pinned video, avoiding the fragile build-time YouTube request. They do not copy any
prior rollout, solution, reward, or calibration data into the task copy.

The temporary task still contains the answer key under `steps/solve/tests/` because
Harbor needs it for verification. Harbor mounts that directory at `/tests` only
after the agent phase; it is not present in the model-visible `/workspace`.

## Common preparation

Run from the repository root. Use the exact 1280x720@50 video with SHA256
`076bcc59fc48443d24a72a87162021470b9e645b41c858c3ffa5b5b25bae36cd`.

```bash
export PATH=/Users/zsj/.local/bin:/Users/zsj/.local/share/uv/tools/harbor/bin:$PATH
export DOCKER_HOST=unix:///Users/zsj/.colima/default/docker.sock
export ROBOCUP_VIDEO=/Users/zsj/Documents/robot-football-codex-v2/match.mp4

docker version
harbor --version  # must report 0.20.0
shasum -a 256 "$ROBOCUP_VIDEO"
git status --short
git rev-parse HEAD
```

Do not paste the task prompt into either agent, append hints, open the public match
page during the run, or expose any of these to the model:

- `steps/solve/tests/ground_truth.json`
- `tools/ground_truth_audit.json`
- `steps/solve/solution/solution.json`
- old agent solutions, trajectories, scores, or reviewer discussion

Each wrapper makes exactly one model attempt with retries disabled. Setup or
transport failures may be fixed and rerun only when no model response was produced.
Never rerun a completed response because its score is too high.

`MANUAL_RUN_MANIFEST.json` records both the overall worktree state and
`scored_payload_dirty`. The latter must be `false`; calibration documentation may be
uncommitted without changing the instruction, task config, or verifier payload.

The shipped agent timeout is 3600 seconds. Leave `AGENT_TIMEOUT_MULTIPLIER` unset for
the qualification result. If an infrastructure diagnostic needs a longer timeout,
set it explicitly and label that run as a timeout-extended diagnostic rather than
the shipped configuration.

## Exact metric

The verifier reward is strict exact IoU over full-chain matches. A prediction earns
credit only when every field in the chain matches an order-preserving ground-truth
entry. The score is `matches / (submitted + ground truth - matches)`, so it penalizes
both unreported and extra entries. `collect_run.py` records exact IoU together with
precision and recall diagnostics; there is no partial-credit reward.

After a successful run, each wrapper writes `manual-run-summary.json` under its job
directory. It records exact IoU, precision, recall, the ATIF tool-call count, versions, and
whole-file SHA256 values. Inspect the credential scan before publishing a raw or
scrubbed trajectory.

Use the generated UTC job name to inspect the result and locate the raw trajectory:

```bash
cat jobs/robocup-claude-final-<UTC>/manual-run-summary.json
find jobs/robocup-claude-final-<UTC> -type f -name 'trajectory.json' -print
```

Replace the prefix with `robocup-antigravity-final-` for Antigravity. Keep the whole
job directory until the score, trajectory hash, and credential scan have been copied
into `calibration/scores.md` and the trajectory has been published as a release asset.

See `claude/README.md` and `antigravity/README.md` for authentication and commands.
