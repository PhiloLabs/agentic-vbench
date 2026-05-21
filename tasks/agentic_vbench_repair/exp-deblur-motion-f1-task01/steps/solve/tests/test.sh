#!/bin/bash
# Verifier: masked metrics — in-mask quality vs clean, out-mask preservation vs corrupted.
set -euo pipefail

mkdir -p /logs/verifier /logs/artifacts

if [ -d /workspace/output ]; then
    cp -a /workspace/output/. /logs/artifacts/ 2>/dev/null || true
fi

python3 -c "import cv2, numpy, skimage, colour" 2>/dev/null || \
    pip install --quiet --no-cache-dir "numpy<3" \
        "opencv-python-headless==4.13.*" \
        "scikit-image==0.26.*" \
        "colour-science==0.4.*"

WIN_ARG=()
if [ -f /tests/gt_window.json ]; then
    WIN_ARG=(--gt-window-json /tests/gt_window.json)
fi

cp -r /baked/golden/. /tests/

python3 /tests/judge.py \
        --output-mp4 /workspace/output/output.mp4 \
        --clean-mp4 /tests/clean.mp4 \
        --corrupted-mp4 /workspace/materials/corrupted.mp4 \
        --mask-png /tests/mask.png \
        --task-type deblur \
        "${WIN_ARG[@]}" \
        --reward-json /logs/verifier/reward.json \
        --reward-txt /logs/verifier/reward.txt
