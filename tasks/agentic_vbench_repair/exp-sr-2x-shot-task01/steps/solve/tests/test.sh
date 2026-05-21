#!/bin/bash
# Verifier: shot-scoped SR judge — PSNR-Y/SSIM-Y in shot, IoU, out-PSNR.
set -euo pipefail

mkdir -p /logs/verifier /logs/artifacts

if [ -d /workspace/output ]; then
    cp -a /workspace/output/. /logs/artifacts/ 2>/dev/null || true
fi

python3 -c "import cv2, numpy, skimage" 2>/dev/null || \
    pip install --quiet --no-cache-dir "numpy<3" "opencv-python-headless==4.13.*" "scikit-image>=0.22"

cp -r /baked/golden/. /tests/

python3 /tests/judge.py \
        --output-mp4 /workspace/output/output.mp4 \
        --output-json /workspace/output/output.json \
        --gt-shot-json /tests/gt_shot.json \
        --corrupted /workspace/materials/corrupted.mp4 \
        --original /tests/original.mp4 \
        --reward-json /logs/verifier/reward.json \
        --reward-txt /logs/verifier/reward.txt
