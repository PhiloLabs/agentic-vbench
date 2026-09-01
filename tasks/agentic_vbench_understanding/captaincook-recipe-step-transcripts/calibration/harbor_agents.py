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

Everything else is stock 0.21.0: the install command, the credential handling, the
trajectory capture, the egress control. What this changes is two strings.
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

    def build_cli_flags(self) -> str:
        flags = super().build_cli_flags()
        if not self._reasoning_effort:
            return flags
        effort = f"--effort {shlex.quote(self._reasoning_effort)}"
        return f"{flags} {effort}" if flags else effort
