#!/bin/bash
set -euo pipefail

mkdir -p /logs/verifier /logs/artifacts
if [ -d /workspace/output ]; then
    cp -a /workspace/output/. /logs/artifacts/ 2>/dev/null || true
fi

python3 /tests/judge.py \
    --solution /workspace/output/solution.json \
    --reward-json /logs/verifier/reward.json \
    --reward-txt /logs/verifier/reward.txt \
    --details-json /logs/verifier/verifier-details.json
