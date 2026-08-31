#!/bin/bash
set -euo pipefail

mkdir -p /logs/verifier /logs/artifacts
if [ -f /workspace/output/solution.json ]; then
    cp /workspace/output/solution.json /logs/artifacts/solution.json
fi

python3 /tests/judge.py \
    --ground-truth /tests/ground_truth.json \
    --solution /workspace/output/solution.json \
    --reward-json /logs/verifier/reward.json \
    --reward-txt /logs/verifier/reward.txt
