#!/bin/bash
# Verifier: shot-scoped SR judge — PSNR-Y/SSIM-Y in shot, IoU, out-PSNR.
set -euo pipefail

mkdir -p /logs/verifier /logs/artifacts

if [ -d /workspace/output ]; then
    cp -a /workspace/output/. /logs/artifacts/ 2>/dev/null || true
fi

python3 -c "import cv2, numpy, skimage" 2>/dev/null || \
    pip install --quiet --no-cache-dir "numpy<3" "opencv-python-headless==4.13.*" "scikit-image>=0.22"

# Fetch golden assets at verifier time. MATERIALS_URL is injected via
# [steps.verifier.env] in task.toml — not visible to the agent step.
mkdir -p /tests /tmp/g
curl --fail --silent --show-error --location --retry 5 --retry-delay 3 \
     "$MATERIALS_URL" -o /tmp/g.zip
unzip -q /tmp/g.zip 'golden/*' -d /tmp/g
cp -r /tmp/g/golden/. /tests/
rm -rf /tmp/g.zip /tmp/g

python3 /tests/judge.py \
        --output-mp4 /workspace/output/output.mp4 \
        --output-json /workspace/output/output.json \
        --gt-shot-json /tests/gt_shot.json \
        --corrupted /workspace/materials/corrupted.mp4 \
        --original /tests/original.mp4 \
        --reward-json /logs/verifier/reward.json \
        --reward-txt /logs/verifier/reward.txt
