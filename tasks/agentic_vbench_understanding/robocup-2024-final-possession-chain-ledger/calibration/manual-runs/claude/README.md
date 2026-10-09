---
title: Claude Code manual run
summary: Authentication and one-command Harbor execution for the Claude calibration.
read_when: Running RoboCup with Claude Code using Opus 4.8 or Fable 5.
---

# Claude Code

For a self-contained brief that can be handed directly to Claude Code App, use
`APP_HANDOFF.md`. It separates endpoint/runtime research from the single clean
benchmark attempt and defines the evidence required for review.

Use an Anthropic key with access to the selected model. Do not put the key in an
`.env` file or command-line literal. The wrapper passes an environment-variable
reference to Harbor and the retained job config records the placeholder, not the
key value.

```bash
export ANTHROPIC_API_KEY='your key in this shell only'
export CLAUDE_CODE_VERSION=2.1.241
export CLAUDE_MODEL=anthropic/claude-opus-4-8

bash tasks/agentic_vbench_understanding/robocup-2024-final-possession-chain-ledger/\
calibration/manual-runs/claude/run.sh
```

For an Anthropic-compatible gateway, set its base URL and host explicitly. Use the
gateway's exact model identifier without a provider prefix:

```bash
export ANTHROPIC_BASE_URL=https://tokken.cc/v1
export ANTHROPIC_API_HOST=tokken.cc
export CLAUDE_MODEL=claude-opus-4-8
```

`anthropic/claude-fable-5` may replace Opus 4.8, but select the model before the run
and do not change it after seeing a result. The wrapper leaves the key in the current
shell environment; Harbor's Claude adapter reads it from the host and injects it into
the isolated agent container, so the key is not placed in a command-line argument or
task file. The runtime uses `reasoning_effort=xhigh`, one attempt, zero Harbor
retries, normal Claude tools, and the checked-in 3600-second timeout unless
`AGENT_TIMEOUT_MULTIPLIER` is explicitly set.

Version `2.1.241` was resolved from the npm registry and preflighted on 2026-08-25.
Recheck availability before a later run, but keep the recorded value fixed once the
calibration attempt starts.

On completion, record:

- job and trial directory;
- Claude Code version and exact model identifier;
- exact reward and exact IoU;
- raw ATIF trajectory and whole-file SHA256;
- tool-call turns and the ATIF record type;
- solution, verifier details, image ID, task commit, and task checksum.

Unset the credential after the run:

```bash
unset ANTHROPIC_API_KEY
```
