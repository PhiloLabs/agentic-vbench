#!/bin/bash
# Oracle: write the verified trade-kill ledger as solution.json.
#
# The reference answer is derived deterministically from the match's own .dem replay
# file (the game server's event log) by provenance/build_gt.py, which also asserts
# verifier(oracle) == 1.0. Like the family's other oracles, this is the verified
# answer key, not an echo of the input. The agent never sees this file or the .dem.
set -euo pipefail

mkdir -p /workspace/output
cp "$(dirname "$0")/oracle_ledger.json" /workspace/output/solution.json
echo "oracle: wrote /workspace/output/solution.json"
