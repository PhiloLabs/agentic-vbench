#!/usr/bin/env bash
# Pin Harbor to a known version so trial outputs are reproducible.
# Bump HARBOR_VERSION when intentionally upgrading; check release notes at
# https://github.com/laude-institute/harbor/releases.
set -euo pipefail

HARBOR_VERSION="0.6.6"

uv tool install --force "harbor[modal]==${HARBOR_VERSION}"
harbor --version
