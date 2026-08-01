#!/bin/bash
# Oracle: write the verified command ledger as solution.json.
#
# oracle_solution.json is the adjudicated, human-reviewed command ledger for the baked
# window (see "Ground truth" in RUNBOOK.md) — the verified answer key, not an echo of
# the input.
# The agent never sees this file.
set -euo pipefail

mkdir -p /workspace/output
cp "$(dirname "$0")/oracle_solution.json" /workspace/output/solution.json

echo "oracle: wrote /workspace/output/solution.json"
