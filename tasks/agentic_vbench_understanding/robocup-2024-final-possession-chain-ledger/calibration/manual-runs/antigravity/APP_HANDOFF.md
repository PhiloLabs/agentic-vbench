---
title: Antigravity App handoff for RoboCup calibration
summary: Self-contained research and execution brief for one clean Antigravity calibration attempt.
read_when: Handing the RoboCup task to Antigravity App or CLI to diagnose OAuth/model access and, only if ready, run the benchmark once.
---

# Objective

Prepare and execute one review-quality Antigravity calibration attempt for the RoboCup
possession-chain task. First prove that the Antigravity CLI can authenticate and
complete a real model request through the selected Gemini route. Only after that
infrastructure check succeeds may you start the benchmark attempt.

Work from this repository:

```text
/Users/zsj/Documents/agentic-vbench-pr
```

The task is:

```text
tasks/agentic_vbench_understanding/robocup-2024-final-possession-chain-ledger
```

Do not modify `task.toml`, `steps/solve/instruction.md`, the verifier, ground truth,
or source video. Do not commit, push, open a pull request, or publish a release asset
unless the user separately authorizes it.

# Required identities

The following values are locked:

| item | required value |
|---|---|
| task commit | `7553740b95925b21a11000ec4d7256c127020577` |
| Harbor | `0.20.0` |
| preferred model | `google/gemini-3.1-pro` through Antigravity, or `google/gemini-3.5-flash` if explicitly selected before the run |
| reasoning | `high` |
| instruction SHA256 | `d6ef93d5679730e84a0d2f94d375f101106bade4f887215d3afdf02c073cd912` |
| judge SHA256 | `8369ebbca7572931961f88ee34937fd656aeb22349a3fb70114d787e18940fc6` |
| ground-truth SHA256 | `5102fa7512efae1ec057f476eb571b99f44d7635158a611465d051417ce67c2e` |
| video SHA256 | `076bcc59fc48443d24a72a87162021470b9e645b41c858c3ffa5b5b25bae36cd` |
| agent timeout | `3600` seconds; leave `AGENT_TIMEOUT_MULTIPLIER` unset |
| attempts/retries | one attempt, zero retries |

The expected video path on this machine is:

```text
/Users/zsj/Documents/robot-football-codex-v2/match.mp4
```

# Non-negotiable isolation rules

During the benchmark agent phase, the model may see only the unchanged instruction
and `/workspace/materials/match.mp4`. Harbor may retain verifier files for the later
verifier phase, but they must never appear in `/workspace` during agent execution.

Never expose any of the following to the benchmark model:

- `steps/solve/tests/ground_truth.json`;
- `tools/ground_truth_audit.json`;
- `steps/solve/solution/solution.json`;
- old solutions, rewards, trajectories, scores, ablation outputs, or reviewer text;
- public match pages, online logs, replay files, statistics, or results;
- hints, corrections, expected scores, or summaries of earlier agent behavior.

The benchmark attempt must not use web search, external sources, or user assistance.
Do not paste or rewrite the task prompt. Use the exact checked-in instruction. Do not
rerun a completed model response because its score is high. A setup or transport
failure may be repaired and retried only when it produced no substantive model
response; retain the failed diagnostic and explain it separately.

# OAuth and credential rules

Antigravity uses a Google OAuth token file, not a Gemini API key. Never ask the user
to paste an OAuth token into chat. Never print, read back, persist in git, or inspect
the token contents. Keep the host token file mode `600`, use Harbor's credential
upload path, and delete the host token after the run if it was created solely for this
calibration.

Do not expose the token file, browser profile, prior Antigravity sessions, old outputs,
or calibration directories to the model. Before publishing a trajectory, run the
provided credential scan. If it finds a token pattern, stop and report only the file
path, not the secret.

# Phase 1: infrastructure research only

This phase must not use the benchmark instruction or video. Use an empty temporary
directory or a harmless scratch task.

1. Inspect Harbor and Antigravity CLI versions. The preflight observed `agy 1.1.20`
   on 2026-08-25, but the installer is not version-pinnable; record the actual version
   from the run.
2. Confirm Docker/Colima is available.
3. Run `harbor agy login` into a new temporary token path with permissions `600`.
4. Run a minimal Antigravity smoke test in an empty task. Request a tiny local action,
   such as writing and reading a file containing `OK`. Do not use RoboCup files or
   prompt content.
5. Require all of the following before proceeding:
   - OAuth succeeds without exposing token contents;
   - the selected model returns real input and output tokens;
   - at least one normal Antigravity tool action succeeds;
   - there is no auth failure, model-not-found error, HTTP 4xx/5xx, transport error,
     synthetic response, or nonzero agent exit;
   - the CLI and Harbor logs identify the exact model and installed `agy` version;
   - the native Antigravity trajectory is captured.

A direct Gemini API or a successful login alone is insufficient. The smoke test must
exercise the same Antigravity CLI adapter and OAuth path used by the benchmark.

If Phase 1 fails, stop before the benchmark. Report the exact non-secret error,
selected model, `agy` version, and missing capability. Do not replace Antigravity with
a direct API script or classify the failure as a benchmark score.

# Phase 2: clean benchmark attempt

Proceed only after Phase 1 passes. Use the audited wrapper rather than an ordinary
interactive App conversation:

```bash
cd /Users/zsj/Documents/agentic-vbench-pr

export PATH=/Users/zsj/.local/bin:/Users/zsj/.local/share/uv/tools/harbor/bin:$PATH
export DOCKER_HOST=unix:///Users/zsj/.colima/default/docker.sock
export ROBOCUP_VIDEO=/Users/zsj/Documents/robot-football-codex-v2/match.mp4

export AGY_AUTH_JSON_PATH="$HOME/.gemini/antigravity-cli/robocup-harbor-token"
harbor agy login --output "$AGY_AUTH_JSON_PATH"
chmod 600 "$AGY_AUTH_JSON_PATH"

export ANTIGRAVITY_MODEL=google/gemini-3.1-pro

bash tasks/agentic_vbench_understanding/robocup-2024-final-possession-chain-ledger/\
calibration/manual-runs/antigravity/run.sh
```

`google/gemini-3.5-flash` is allowed only if selected before the run and recorded as
the exact model. Do not change models after seeing any result. Do not set a fixed
`JOB_NAME`; let the wrapper create a UTC-stamped unique name.

Before Harbor starts, inspect `MANUAL_RUN_MANIFEST.json`. Abort if
`scored_payload_dirty` is not `false`, or if any locked hash differs.

The wrapper must retain these settings:

- Docker environment through Harbor 0.20;
- exact local video verified by SHA256;
- selected Gemini model fixed before scoring;
- `reasoning_effort=high`;
- normal Antigravity CLI tools;
- one attempt, one concurrent trial, zero retries;
- only the required Google/Antigravity service hosts allowed;
- checked-in 3600-second timeout;
- raw agent logs, native Antigravity trajectory, ATIF trajectory, and solution artifact.

# Result validity

A run is a valid model attempt only if Antigravity produced a substantive model
response and the task reached normal completion or a genuine post-response timeout.
Do not classify infrastructure failures as scores.

Invalid examples include:

- zero model input/output tokens;
- OAuth, model-not-found, endpoint, transport, installer, or container failure;
- missing `solution.json` caused by agent startup/auth failure;
- verifier `0.0` produced only because the answer file is absent;
- a rewritten prompt, exposed ground truth, external match lookup, or user hints;
- a completed response rerun after its score is known.

After a valid run, `collect_run.py` creates `manual-run-summary.json`. Report both:

- exact IoU, plus precision and recall diagnostics, from strict full-chain matches.

Exact IoU is the only score. The strong-agent difficulty gate is exact IoU below `0.10`. Also report whether the attempt exceeded roughly 50
tool-call turns; a shorter genuine completion is not automatically invalid, but it
must be described accurately.

# Required evidence and final report

Preserve the whole job directory and do not overwrite the raw trajectory. Report:

1. whether Phase 1 passed, exact model, Harbor, and `agy` versions;
2. job/trial directory paths and OAuth handling without printing token data;
3. task commit, task checksum, image ID, and all locked file hashes;
4. start/end timestamps and final status;
5. exact IoU, precision, and recall;
6. prediction count, schema-valid count, and exact matches;
7. ATIF tool-call turns, raw tool-call count, and the counting record type;
8. native trajectory path and whole-file SHA256, plus ATIF trajectory SHA256;
9. solution, verifier details, and reward file SHA256s;
10. credential-scan result and confirmation that no secret was printed;
11. any infrastructure failure, clearly separated from scored results.

Do not edit `calibration/scores.md` until the user confirms the run should be adopted.
End with the path to `manual-run-summary.json` and one of:
`valid calibration attempt` or `invalid infrastructure diagnostic`, with the concrete
reason.
