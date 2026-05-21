#!/bin/bash
# Verifier: per-slot scoring with SSIM-honesty gate. Judges both
# /workspace/output/solution.json (slot picks) AND
# /workspace/output/solution.mp4 (actual concatenated video) against
# the materials in /workspace/materials/.
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
