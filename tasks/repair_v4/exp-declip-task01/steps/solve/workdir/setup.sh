#!/bin/bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
mkdir -p /workspace/materials /workspace/output /workspace/work
cp "$HERE/noisy.wav" /workspace/materials/noisy.wav
mkdir -p /logs/artifacts
ls -la /workspace/materials/ > /logs/artifacts/materials-listing.txt
rm -f -- "$HERE/noisy.wav" "$0"
