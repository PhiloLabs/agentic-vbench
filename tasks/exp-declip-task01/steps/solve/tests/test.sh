#!/bin/bash
set -euo pipefail
mkdir -p /logs/verifier /logs/artifacts
if [ -d /workspace/output ]; then
    cp -a /workspace/output/. /logs/artifacts/ 2>/dev/null || true
fi
pip install --quiet --no-cache-dir \
    "numpy<3" "scipy<2" "soundfile==0.13.*" "pesq==0.0.4" "pystoi==0.4.*"
python3 /tests/judge.py \
        --enhanced /workspace/output/enhanced.wav \
        --clean /tests/clean.wav \
        --clip-mask /tests/clip_mask.npy \
        --window-json /tests/window.json \
        --reward-json /logs/verifier/reward.json \
        --reward-txt /logs/verifier/reward.txt
