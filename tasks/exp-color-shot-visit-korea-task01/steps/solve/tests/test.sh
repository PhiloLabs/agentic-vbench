#!/bin/bash
# Verifier: deterministic windowed color-restoration judge (LAB ΔE).
set -euo pipefail

mkdir -p /logs/verifier /logs/artifacts

if [ -d /workspace/output ]; then
    cp -a /workspace/output/. /logs/artifacts/ 2>/dev/null || true
fi

python3 /tests/judge.py \
        --output-mp4 /workspace/output/output.mp4 \
        --source-mp4 /workspace/materials/source.mp4 \
        --original-mp4 /tests/original.mp4 \
        --gt-window-json /tests/gt_window.json \
        --reward-json /logs/verifier/reward.json \
        --reward-txt /logs/verifier/reward.txt
