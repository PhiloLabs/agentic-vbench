---
title: Claude Code App handoff for RoboCup calibration
summary: Self-contained research and execution brief for a clean Claude Code calibration attempt.
read_when: Handing the RoboCup task to Claude Code App to diagnose its runtime and, only if ready, run the benchmark once.
---

# Objective

Prepare and execute one review-quality Claude Code calibration attempt for the
RoboCup possession-chain task. First prove that the selected Claude Code runtime can
reach the configured model through its API endpoint. Only after that infrastructure
check succeeds may you start the benchmark attempt.

Work from this repository:

```text
/Users/zsj/Documents/agentic-vbench-pr
```

The task is located at:

```text
tasks/agentic_vbench_understanding/robocup-2024-final-possession-chain-ledger
```

Do not modify `task.toml`, `steps/solve/instruction.md`, the verifier, ground truth,
or source video. Do not commit, push, open a pull request, or publish an asset unless
the user separately authorizes it.

# Required identities

The following values are locked:

| item | required value |
|---|---|
| task commit | `7553740b95925b21a11000ec4d7256c127020577` |
| Harbor | `0.20.0` |
| Claude Code | `2.1.241` |
| preferred model | `claude-opus-4-8` through a compatible gateway, or `anthropic/claude-opus-4-8` through the official API |
| reasoning | `xhigh` |
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

The benchmark attempt must not use WebSearch, WebFetch, browser tools, external
sources, or user assistance. Do not paste or rewrite the task prompt. Use the exact
checked-in instruction. Do not rerun a completed model response because its score is
high. A transport or setup failure may be retried only when it produced zero model
tokens and no substantive model response, and the failed infrastructure diagnostic
must remain documented.

# Credential rules

Ask the user to export credentials in their shell if they are not already present.
Never ask the user to paste a credential into chat. Never print, read back, persist,
or inspect the credential value. Do not place a literal credential in a command-line
argument, task file, `.env` file, trajectory, report, or git diff. Harbor agent
configuration must contain `${ANTHROPIC_API_KEY}`, not the resolved value.

Before publishing any trajectory, run the provided credential scan. If any token is
found, stop and report the affected file without printing the token.

# Phase 1: infrastructure research only

This phase must not use the benchmark instruction or video. Its purpose is to prove
that Claude Code itself, not only a simple `curl`, can complete a streamed tool-capable
request through the selected endpoint.

1. Inspect the installed/runtime versions of Claude Code and Harbor.
2. Confirm Docker or Colima is available.
3. Determine whether the user is using the official Anthropic API or a compatible
   gateway. Do not reveal its credential.
4. Run a minimal Claude Code smoke test in an empty temporary directory. The test
   prompt should request a tiny local action such as creating a text file containing
   `OK`, then reading it back. Do not use any RoboCup files or prompt content.
5. Require all of the following before proceeding:
   - the requested model returns real input and output tokens;
   - at least one normal Claude Code tool call succeeds;
   - there is no `model_not_found`, HTTP 4xx/5xx, synthetic error response, or
     nonzero agent exit;
   - the CLI reports the exact model and Claude Code version used;
   - streaming completes normally.

A plain successful `curl /v1/messages` is insufficient. Claude Code may send tools,
streaming, system instructions, thinking/effort settings, beta headers, and other
fields that a basic Messages compatibility layer does not support.

For a compatible gateway, these are the intended environment shapes; use values
already exported by the user rather than embedding secrets:

```bash
export ANTHROPIC_BASE_URL=https://tokken.cc/v1
export ANTHROPIC_API_HOST=tokken.cc
export CLAUDE_MODEL=claude-opus-4-8
```

Known diagnostic evidence: a previous Claude Code `2.1.241` attempt against that
gateway reached the CLI but received HTTP 404 `model_not_found`, with zero input and
output tokens. Its verifier-generated `0.0` is invalid as a model score because no
`solution.json` was produced. Do not report or reuse that value as a baseline.

If the smoke test fails, stop before the benchmark. Report the exact non-secret error,
the model ID, endpoint host, Claude Code version, and which compatibility capability
appears missing. Do not weaken the benchmark or replace Claude Code with a direct API
script.

# Phase 2: clean benchmark attempt

Proceed only after Phase 1 passes. Use the existing audited wrapper rather than an
ordinary interactive IDE conversation:

```bash
cd /Users/zsj/Documents/agentic-vbench-pr

export PATH=/Users/zsj/.local/bin:/Users/zsj/.local/share/uv/tools/harbor/bin:$PATH
export DOCKER_HOST=unix:///Users/zsj/.colima/default/docker.sock
export ROBOCUP_VIDEO=/Users/zsj/Documents/robot-football-codex-v2/match.mp4
export CLAUDE_CODE_VERSION=2.1.241

# Official Anthropic API:
export CLAUDE_MODEL=anthropic/claude-opus-4-8

# For the compatible gateway instead, use:
# export ANTHROPIC_BASE_URL=https://tokken.cc/v1
# export ANTHROPIC_API_HOST=tokken.cc
# export CLAUDE_MODEL=claude-opus-4-8

bash tasks/agentic_vbench_understanding/robocup-2024-final-possession-chain-ledger/\
calibration/manual-runs/claude/run.sh
```

Do not set a fixed `JOB_NAME`; allow the wrapper to create its UTC-stamped unique job
name. Before Harbor starts, inspect `MANUAL_RUN_MANIFEST.json`. Abort if
`scored_payload_dirty` is not `false`, or if any locked hash differs.

The wrapper must retain these settings:

- Docker environment through Harbor 0.20;
- exact local video verified by SHA256;
- Claude Code `2.1.241`;
- selected model fixed before seeing the result;
- `reasoning_effort=xhigh`;
- normal Claude Code local tools;
- one attempt, one concurrent trial, zero retries;
- no agent internet except the selected model API host;
- checked-in 3600-second timeout;
- raw agent logs and `/workspace/output/solution.json` as an artifact.

# Result validity

A run is a valid model attempt only if Claude Code received a substantive model
response and the task reached a normal completion or a genuine post-response agent
timeout. Do not classify infrastructure failures as scores.

Invalid examples include:

- zero model input/output tokens;
- `model_not_found`, authentication, endpoint, transport, or installer failure;
- missing `solution.json` caused by an agent startup/API error;
- verifier `0.0` produced only because the answer file is absent;
- a rewritten prompt, exposed ground truth, external match lookup, or user hints;
- a completed response rerun after its score is known.

After a valid run, the wrapper calls `collect_run.py` and creates
`manual-run-summary.json`. Report the exact metrics:

- exact IoU, plus precision and recall diagnostics, from strict full-chain matches.

Exact IoU is the only score. The strong-agent difficulty gate is exact IoU below `0.10`. Also report whether the attempt exceeded roughly 50
tool-call turns; a shorter genuine completion is not automatically invalid, but it
must be described accurately.

# Required evidence and final report

Preserve the whole job directory. Do not summarize away or overwrite the raw
trajectory. The final report to the user must include:

1. whether Phase 1 passed and the exact endpoint host/model/runtime versions;
2. job and trial directory paths;
3. task commit, task checksum, image ID, and the four locked file hashes;
4. start/end timestamps and final status;
5. exact IoU, precision, and recall;
6. prediction count, schema-valid count, and exact matches;
8. ATIF tool-call turns, raw tool-call count, and the counting record type;
9. full paths, byte sizes, and whole-file SHA256s for solution, verifier details,
   reward, and raw trajectory;
10. credential-scan result and confirmation that no secret was printed;
11. any deviation or infrastructure failure, clearly separated from scored results.

Do not edit `calibration/scores.md` until the user confirms the run should be adopted.
End by giving the user the path to `manual-run-summary.json` and a concise validity
judgment: `valid calibration attempt` or `invalid infrastructure diagnostic`, with
the concrete reason.
