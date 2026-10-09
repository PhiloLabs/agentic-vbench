#!/usr/bin/env python3
"""What Harbor's antigravity-cli adapter does not do for `agy`, added through Harbor's own
extension point.

    harbor run -a calibration.harbor_agents:AntigravityCliWithEffort ...

Antigravity is the family's third calibration harness, and it has to run inside the task
image. Harbor 0.20/0.21 carry an `antigravity-cli` adapter that installs `agy` in the
container and seeds a pre-provisioned OAuth token, which is the only headless credential
`agy` accepts: it has no API-key path and its sign-in is an interactive browser flow.

That adapter never passes `--effort`, and `agy` 1.1.22 refuses to start:

    Error: invalid model selection (--model "gemini-3.6-flash" --effort ""):
    --model gemini-3.6-flash requires --effort (available: low, medium, high)

The adapter does read `reasoning_effort`. It writes a `harbor-<model>-<effort>` alias into
`~/.agy/antigravity-cli/settings.json` with the right `thinkingLevel`, then passes the raw
model name on the command line instead of the alias, so the setting is never reached.

The release that added `--effort`, 0.21.1.dev202608202357, removed the OAuth-token seeding
in the same release and authenticates only from an API key or Application Default
Credentials. Every release was checked: none does both. So this file adds the missing flag
through the `module:ClassName` agent path Harbor documents on `--agent`.

There is a second flag, for a second reason. `agy --print-timeout` defaults to five
minutes, and it is the agent's own cap on how long one `--print` run may take. It does not
know about the budget Harbor grants, so without it every arm ends at five minutes with
`Error: timeout waiting for response`, whatever the task allows. A probe run ended exactly
that way. This subclass declares the flag so it can be set from the command line and land
in the record; the value passed is the task's own `steps.agent.timeout_sec`, not a number
chosen here.

There is a third thing, and it is not a flag. The adapter copies the raw trajectory out
of `~/.agy/antigravity-cli/tmp/session-*.jsonl`, which is where agy 1.1.8 kept it. agy
1.1.22 and 1.2.2 write it to

    ~/.gemini/antigravity-cli/brain/<session>/.system_generated/logs/transcript_full.jsonl

so the copy finds nothing and the run ends with a score and no auditable trajectory. The
family's rule is that a summary cannot be audited, and the turn-count gate is counted off
that file, so a missing one is not a cosmetic loss. This subclass copies it from where agy
actually writes it, and says so loudly if there is nothing there.

The fourth was found by this task's first Antigravity attempt. `agy` 1.2.2 gives the model
`invoke_subagent` and `manage_subagents`, and that attempt used them to hand the match to
four subagents, one per quarter, which breaks the one-agent protocol every arm runs under.
`agy` has no flag that removes a tool, so before the run this subclass writes
`calibration/antigravity_hooks.json` to `~/.gemini/config/hooks.json`, agy's global
customization directory. Its one PreToolUse hook denies any tool whose name contains
"subagent" before the tool runs. Claude Code's arm gets the same guarantee from
`--disallowedTools`, and `calibration/probe_antigravity_hook.py` shows the hook refusing a
subagent that the same prompt starts without it.

Every session agy records is copied to /logs/agent/sessions, so a run in which the hook did
not hold shows it in its own artifacts. The trajectory is the session whose first request
carries the instruction's title.

Everything else is stock 0.21.0: the install command, the credential handling, the egress
control.
"""
from __future__ import annotations

import shlex
from pathlib import Path

from harbor.agents.installed.antigravity_cli import AntigravityCli
from harbor.agents.installed.base import CliFlag

HOOKS = (Path(__file__).resolve().parent / "antigravity_hooks.json").read_text()


class AntigravityCliWithEffort(AntigravityCli):
    """Stock antigravity-cli, plus what agy needs to run as one agent to the budget."""

    CLI_FLAGS = [
        *AntigravityCli.CLI_FLAGS,
        # A Go duration string, e.g. "6h". Passed explicitly rather than defaulted, so
        # the value is visible in the command and in the manifest.
        CliFlag("print_timeout", cli="--print-timeout", type="str"),
    ]

    @staticmethod
    def name() -> str:
        return "antigravity-cli"

    # Where agy keeps each session's own step-by-step record. Found by running the CLI in a
    # container and looking, not by reading, because the adapter's own path is from an older
    # CLI and reading it would have reproduced the same mistake.
    _BRAIN = "$HOME/.gemini/antigravity-cli/brain"

    async def run(self, instruction, environment, context):  # type: ignore[override]
        self._title = instruction.strip().splitlines()[0]
        await self.exec_as_agent(
            environment,
            command=(f"mkdir -p ~/.gemini/config && printf %s {shlex.quote(HOOKS)} "
                     f"> ~/.gemini/config/hooks.json"),
        )
        failed = False
        try:
            await super().run(instruction, environment, context)
        except Exception:
            failed = True
            raise
        finally:
            copied = await self._capture_transcript(environment)
            if not copied and not failed:
                raise RuntimeError(
                    "the agent finished but no transcript was captured from "
                    f"{self._BRAIN}; the run cannot be audited and its turn count "
                    "cannot be counted, so it is not a result")

    async def _capture_transcript(self, environment) -> bool:
        """Copy every session to /logs/agent/sessions and the main one beside it."""
        dest = "/logs/agent/antigravity-cli.trajectory.jsonl"
        title = shlex.quote(getattr(self, "_title", ""))
        try:
            await self.exec_as_agent(
                environment,
                command=(
                    'mkdir -p /logs/agent/sessions; main=""; '
                    f'for f in {self._BRAIN}/*/.system_generated/logs/transcript_full.jsonl; do '
                    '[ -f "$f" ] || continue; '
                    'id=$(basename "$(dirname "$(dirname "$(dirname "$f")")")"); '
                    'cp "$f" "/logs/agent/sessions/$id.jsonl"; '
                    f'if head -c 20000 "$f" | grep -qF -- {title}; then main="$f"; fi; '
                    'done; '
                    f'if [ -n "$main" ]; then cp "$main" {dest}; fi'
                ),
            )
            check = await self.exec_as_agent(
                environment,
                command=f'test -s {dest} && wc -l < {dest} || echo 0',
            )
        except Exception:
            return False
        text = getattr(check, "stdout", "") or ""
        try:
            return int(text.strip().splitlines()[-1]) > 0
        except (ValueError, IndexError):
            return False

    def build_cli_flags(self) -> str:
        flags = super().build_cli_flags()
        if not self._reasoning_effort:
            return flags
        effort = f"--effort {shlex.quote(self._reasoning_effort)}"
        return f"{flags} {effort}" if flags else effort
