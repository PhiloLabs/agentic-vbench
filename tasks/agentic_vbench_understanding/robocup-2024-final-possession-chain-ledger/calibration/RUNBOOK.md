---
title: RoboCup clean calibration runbook
summary: Harbor commands for final-image Codex, Claude, and Gemini calibration runs.
read_when: Replacing superseded local rollouts with the clean qualification pass.
---

# Clean calibration runbook

Run from the repository root on a machine with Docker, `uv`, and the three provider
API keys. Harbor reads the checked-in instruction directly; do not paste, append, or
rewrite the prompt.

```bash
TASK=tasks/agentic_vbench_understanding/robocup-2024-final-possession-chain-ledger
TASK_COMMIT=$(git rev-parse HEAD)

test -n "$OPENAI_API_KEY"
test -n "$ANTHROPIC_API_KEY"
test -n "$GEMINI_API_KEY"
docker version
uv tool install --force 'harbor[modal]==0.20.0'
harbor --version

docker build \
  --tag "agentic-vbench-robocup:${TASK_COMMIT}" \
  "$TASK/environment"
docker image inspect \
  --format '{{.Id}}' "agentic-vbench-robocup:${TASK_COMMIT}"
```

Set each CLI adapter version explicitly and record the values in `scores.md`:

```bash
export CODEX_CLI_VERSION=0.147.0-alpha.6.5
export CLAUDE_CODE_VERSION='<installed audited version>'
export GEMINI_CLI_VERSION='<installed audited version>'
```

End-to-end runs:

```bash
harbor run -p "$TASK" -e docker -a codex \
  -m openai/gpt-5.6-sol \
  --ak reasoning_effort=high \
  --ak version="$CODEX_CLI_VERSION" \
  --ae OPENAI_API_KEY="$OPENAI_API_KEY" \
  --job-name robocup-codex-final --yes

harbor run -p "$TASK" -e docker -a claude-code \
  -m anthropic/claude-opus-4-8 \
  --ak reasoning_effort=xhigh \
  --ak version="$CLAUDE_CODE_VERSION" \
  --ae ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
  --job-name robocup-claude-final --yes

harbor run -p "$TASK" -e docker -a gemini-cli \
  -m google/gemini-3.5-flash \
  --ak reasoning_effort=high \
  --ak version="$GEMINI_CLI_VERSION" \
  --ae GEMINI_API_KEY="$GEMINI_API_KEY" \
  --job-name robocup-gemini-final --yes
```

`anthropic/claude-fable-5` may replace Opus 4.8, and
`google/gemini-3.1-pro` may replace Gemini 3.5 Flash, but do not change models within
one reported row. The four Codex degraded-input runs use the same Codex version and
reasoning setting; their exact media/tool conditions are in `ablations/README.md`.

After every run, preserve the output, verifier details, and full ATIF trajectory:

```bash
find jobs/robocup-codex-final -type f \
  \( -name 'solution.json' -o -name 'reward.json' -o -name 'trajectory.json' \) \
  -print
shasum -a 256 /path/to/trajectory.json
```

Publish each unmodified trajectory, or the deterministic output of
`tools/scrub_trajectory.py`, as a fork release asset. Record the release URL,
whole-file SHA256, image ID, task commit, harness/adapter version, model ID,
reasoning setting, and the exact record type used for the tool-call count in
`scores.md`.
