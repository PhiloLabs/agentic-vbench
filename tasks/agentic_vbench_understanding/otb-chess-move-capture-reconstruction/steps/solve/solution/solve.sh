#!/bin/bash
# Oracle solution: copy the canonical answer into the expected output path.
set -euo pipefail

mkdir -p /workspace/output
cp "$(dirname "$0")/solution.json" /workspace/output/solution.json
