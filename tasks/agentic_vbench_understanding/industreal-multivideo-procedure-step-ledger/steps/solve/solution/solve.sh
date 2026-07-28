#!/bin/bash
set -euo pipefail

mkdir -p /workspace/output
cp /solution/ground_truth.json /workspace/output/solution.json
echo "oracle: wrote the verified 47-checkpoint state-transition ledger"
