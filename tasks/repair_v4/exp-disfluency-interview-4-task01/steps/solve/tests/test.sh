#!/bin/bash
# Precision cut verifier: per-cut range gate + global SSIM honesty gate
# + audio xcorr gate. No transcription.
set -euo pipefail

mkdir -p /logs/verifier /logs/artifacts

if [ -d /workspace/output ]; then
    cp -a /workspace/output/. /logs/artifacts/ 2>/dev/null || true
fi

python3 -c "import skimage, numpy" 2>/dev/null || \
    pip install --quiet --no-cache-dir "numpy<3" "scikit-image>=0.22,<1.0"

python3 /tests/judge.py \
        --source-mp4 /workspace/materials/source.mp4 \
        --output-mp4 /workspace/output/output.mp4 \
        --output-cuts /workspace/output/cuts.json \
        --gt-cuts /tests/cuts.json \
        --reward-json /logs/verifier/reward.json \
        --reward-txt /logs/verifier/reward.txt
