#!/bin/bash
# Oracle: write the verified trade-episode ledger as solution.json.
#
# The reference answer is derived deterministically from the match's own .dem
# replay by provenance/build_gt.py, which also asserts verifier(oracle) == 1.0.
# The agent never sees this file or the .dem.
set -euo pipefail

mkdir -p /workspace/output
cp "$(dirname "$0")/oracle_episodes.json" /workspace/output/solution.json
echo "oracle: wrote /workspace/output/solution.json"
