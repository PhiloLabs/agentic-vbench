#!/bin/bash
# Verifier: whole-video PSNR vs original-order reference + diagnostic
# detection IoU.
set -euo pipefail

mkdir -p /logs/verifier /logs/artifacts

if [ -d /workspace/output ]; then
    cp -a /workspace/output/. /logs/artifacts/ 2>/dev/null || true
fi

python3 -c "import cv2, numpy" 2>/dev/null || \
    pip install --quiet --no-cache-dir "numpy<3" "opencv-python-headless==4.13.*"

python3 /tests/judge.py \
        --output-mp4 /workspace/output/output.mp4 \
        --output-json /workspace/output/output.json \
        --original /tests/original.mp4 \
        --gt-swap-json /tests/gt_swap.json \
        --reward-json /logs/verifier/reward.json \
        --reward-txt /logs/verifier/reward.txt
