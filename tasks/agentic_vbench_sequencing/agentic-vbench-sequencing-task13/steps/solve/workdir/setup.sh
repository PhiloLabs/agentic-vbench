#!/bin/bash
# Pre-agent stage: copy pre-baked materials into the agent's workspace.
# (Materials were baked into the image at `docker build` time — see Dockerfile.)
set -euo pipefail

mkdir -p /workspace/materials /workspace/output /workspace/work
cp -r /baked/materials/. /workspace/materials/

mkdir -p /logs/artifacts
ls -la /workspace/materials/ > /logs/artifacts/materials-listing.txt

rm -- "$0"
