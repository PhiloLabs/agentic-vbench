#!/bin/bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p /workspace/output
cp "$script_dir/solution.json" /workspace/output/solution.json

echo "oracle: wrote /workspace/output/solution.json"
