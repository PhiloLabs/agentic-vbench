#!/usr/bin/env python3
"""The one flag Harbor does not pass to `agy`, added through Harbor's own extension point.

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
and nothing else, through the `module:ClassName` agent path Harbor documents on `--agent`.

There is a second flag, for a second reason. `agy --print-timeout` defaults to five
minutes, and it is the agent's own cap on how long one `--print` run may take. It does not
know about the budget Harbor grants, so without it every arm ends at five minutes with
`Error: timeout waiting for response`, whatever the task allows. A probe run ended exactly
that way. This subclass declares the flag so it can be set from the command line and land
in the record; the value passed is the task's own `steps.agent.timeout_sec`, not a number
chosen here.

There is a third thing, and it is not a flag. The adapter copies the raw trajectory out
of `~/.agy/antigravity-cli/tmp/session-*.jsonl`, which is where agy 1.1.8 kept it. agy
1.1.22 writes it to

    ~/.gemini/antigravity-cli/brain/<session>/.system_generated/logs/transcript_full.jsonl

so the copy finds nothing and the run ends with a score and no auditable trajectory. The
family's rule is that a summary cannot be audited, and the turn-count gate is counted off
that file, so a missing one is not a cosmetic loss. This subclass copies it from where agy
1.1.22 actually writes it, and says so loudly if there is nothing there.

Everything else is stock 0.21.0: the install command, the credential handling, the egress
control. What this changes is two flags and one path.
"""
from __future__ import annotations

import shlex

from harbor.agents.installed.antigravity_cli import AntigravityCli
from harbor.agents.installed.base import CliFlag


class AntigravityCliWithEffort(AntigravityCli):
    """Stock antigravity-cli, plus the two flags agy 1.1.22 needs to run to the budget."""

    CLI_FLAGS = [
        *AntigravityCli.CLI_FLAGS,
        # A Go duration string, e.g. "6h". Passed explicitly rather than defaulted, so
        # the value is visible in the command and in the manifest.
        CliFlag("print_timeout", cli="--print-timeout", type="str"),
    ]

    @staticmethod
    def name() -> str:
        return "antigravity-cli"

    # Where agy 1.1.22 keeps the run's own step-by-step record. Found by running the CLI
    # in a container and looking, not by reading, because the adapter's own path is from
    # an older CLI and reading it would have reproduced the same mistake.
    _TRANSCRIPT = ("$HOME/.gemini/antigravity-cli/brain/*/.system_generated/logs/"
                   "transcript_full.jsonl")

    async def run(self, instruction, environment, context):  # type: ignore[override]
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
                    f"{self._TRANSCRIPT}; the run cannot be audited and its turn count "
                    "cannot be counted, so it is not a result")

    async def _capture_transcript(self, environment) -> bool:
        """Copy agy's own record to /logs/agent. Returns whether anything was copied."""
        dest = "/logs/agent/antigravity-cli.trajectory.jsonl"
        try:
            await self.exec_as_agent(
                environment,
                command=(
                    f'src=$(ls -t {self._TRANSCRIPT} 2>/dev/null | head -n1); '
                    f'if [ -n "$src" ]; then cp "$src" {dest}; fi'
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
