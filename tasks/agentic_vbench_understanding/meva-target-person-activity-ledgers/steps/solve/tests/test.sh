#!/bin/bash
set -euo pipefail

mkdir -p /logs/verifier /logs/artifacts

python3 /tests/judge.py \
    --solution /workspace/output/solution.json \
    --ground-truth /tests/ground_truth.json \
    --reward-json /logs/verifier/reward.json \
    --reward-txt /logs/verifier/reward.txt \
    --artifact /logs/artifacts/submitted_solution.json
