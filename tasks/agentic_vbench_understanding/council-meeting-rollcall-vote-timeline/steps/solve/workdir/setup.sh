#!/bin/bash
# Pre-agent stage: copy the pre-baked meeting video into the agent workspace.
set -euo pipefail

mkdir -p /workspace/materials /workspace/output /workspace/work
cp /baked/meeting.mov /workspace/materials/issaquah_city_council_2021-12-06.mov

mkdir -p /logs/artifacts
ls -la /workspace/materials/ > /logs/artifacts/materials-listing.txt

rm -- "$0"
