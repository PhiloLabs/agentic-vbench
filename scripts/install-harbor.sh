#!/usr/bin/env bash
# Pin Harbor to a known version so trial outputs are reproducible.
# Bump HARBOR_VERSION when intentionally upgrading; check release notes at
# https://github.com/laude-institute/harbor/releases.
#
# Extras installed:
#   - modal    — required for `-e modal`   (sandbox runs on Modal)
#   - daytona  — required for `-e daytona` (sandbox runs on Daytona)
# `-e docker` (local) works without any extra. Add more cloud executors
# (e2b, runloop, gke, etc.) by extending the bracketed list below — see
# `harbor run --help` for the full list.
set -euo pipefail

HARBOR_VERSION="0.6.6"

uv tool install --force "harbor[modal,daytona]==${HARBOR_VERSION}"
harbor --version
