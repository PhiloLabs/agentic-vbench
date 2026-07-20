#!/bin/bash
set -euo pipefail

mkdir -p /workspace/output
cp "$(dirname "$0")/solution.json" /workspace/output/solution.json
echo "oracle: wrote /workspace/output/solution.json"
