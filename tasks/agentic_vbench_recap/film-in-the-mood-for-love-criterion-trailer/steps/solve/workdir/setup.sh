#!/bin/bash
# Pre-agent stage: copy pre-baked input files into the agent's workspace.
# Verifier-only assets (rubric.json) stay in /baked/ — kept out of the
# agent's view.
set -euo pipefail

mkdir -p /workspace/materials /workspace/output /workspace/work
cp /baked/source.mp4 /workspace/materials/source.mp4
cp /baked/brief.md   /workspace/materials/brief.md

mkdir -p /logs/artifacts
ls -la /workspace/materials/ > /logs/artifacts/materials-listing.txt

rm -- "$0"
