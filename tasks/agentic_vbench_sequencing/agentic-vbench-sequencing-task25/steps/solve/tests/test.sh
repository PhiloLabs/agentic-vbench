#!/bin/bash
# Verifier: per-slot scoring with SSIM-honesty gate. Reads both
# /workspace/output/solution.json AND /workspace/output/solution.mp4
# and validates against the candidate clips in /workspace/materials/.
set -euo pipefail

mkdir -p /logs/verifier /logs/artifacts
if [ -d /workspace/output ]; then
    cp -a /workspace/output/. /logs/artifacts/ 2>/dev/null || true
fi

python3 /tests/judge.py \
        --solution /workspace/output/solution.json \
        --solution-mp4 /workspace/output/solution.mp4 \
        --materials-dir /workspace/materials \
        --reward-json /logs/verifier/reward.json \
        --reward-txt /logs/verifier/reward.txt
