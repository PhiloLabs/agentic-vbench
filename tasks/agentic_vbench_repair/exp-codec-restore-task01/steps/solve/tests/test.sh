#!/bin/bash
# Verifier: download the per-task materials zip again to extract golden
# references into /tests/, then run judge.py. The golden never lived in
# the agent's container.
set -euo pipefail

mkdir -p /logs/verifier /logs/artifacts /tests

# Republish whatever the agent left under /workspace/output/.
if [ -d /workspace/output ]; then
    cp -a /workspace/output/. /logs/artifacts/ 2>/dev/null || true
fi

cp -r /baked/golden/. /tests/

python3 /tests/judge.py \
        --enhanced /workspace/output/enhanced.wav \
        --clean /tests/clean.wav \
        --dnsmos-model /tests/sig_bak_ovr.onnx \
        --window-json /tests/window.json \
        --reward-json /logs/verifier/reward.json \
        --reward-txt /logs/verifier/reward.txt

