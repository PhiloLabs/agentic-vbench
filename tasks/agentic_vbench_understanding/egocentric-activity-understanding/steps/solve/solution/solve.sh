#!/bin/bash
set -euo pipefail

mkdir -p /workspace/output
cp "$(dirname "$0")/oracle.json" /workspace/output/solution.json
echo "oracle: wrote /workspace/output/solution.json (172 actions)"
