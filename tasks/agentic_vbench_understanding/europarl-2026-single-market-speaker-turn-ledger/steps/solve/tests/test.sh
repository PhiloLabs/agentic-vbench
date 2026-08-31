#!/bin/bash
set -euo pipefail

mkdir -p /logs/verifier

python3 /tests/judge.py \
    --solution /workspace/output/solution.json \
    --reward-json /logs/verifier/reward.json \
    --reward-txt /logs/verifier/reward.txt
