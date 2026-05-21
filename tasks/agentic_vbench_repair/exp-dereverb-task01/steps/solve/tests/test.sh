#!/bin/bash
set -euo pipefail
mkdir -p /logs/verifier /logs/artifacts
if [ -d /workspace/output ]; then
    cp -a /workspace/output/. /logs/artifacts/ 2>/dev/null || true
fi
cp -r /baked/golden/. /tests/

python3 /tests/judge.py \
        --enhanced /workspace/output/enhanced.wav \
        --clean /tests/clean.wav \
        --window-json /tests/window.json \
        --reward-json /logs/verifier/reward.json \
        --reward-txt /logs/verifier/reward.txt
