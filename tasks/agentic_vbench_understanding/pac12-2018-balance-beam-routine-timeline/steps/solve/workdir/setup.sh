#!/bin/bash
set -euo pipefail

expected_sha256="7dfc9e139254cc9480948af734988bdebc796c89c6e5d439055a248c251130cb"

mkdir -p /workspace/materials /workspace/output /workspace/work
# The Docker build already verifies this digest. Check it again at trial setup
# so a corrupted or replaced baked artifact never reaches the agent.
test -f /baked/source.mp4
echo "${expected_sha256}  /baked/source.mp4" | sha256sum -c -
cp /baked/source.mp4 /workspace/materials/source.mp4

mkdir -p /logs/artifacts
ls -la /workspace/materials > /logs/artifacts/materials-listing.txt

rm -- "$0"
