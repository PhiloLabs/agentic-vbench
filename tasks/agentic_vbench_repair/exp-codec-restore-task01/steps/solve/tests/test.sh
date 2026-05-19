#!/bin/bash
# Verifier: download the per-task materials zip again to extract golden
# references into /tests/, then run judge.py. The golden never lived in
# the agent's container.
set -euo pipefail

MATERIALS_URL="https://huggingface.co/datasets/ameddserM/agentic_vbench_repair/resolve/main/materials/exp-codec-restore-task01.zip"

mkdir -p /logs/verifier /logs/artifacts /tests

# Republish whatever the agent left under /workspace/output/.
if [ -d /workspace/output ]; then
    cp -a /workspace/output/. /logs/artifacts/ 2>/dev/null || true
fi

curl --fail --silent --show-error --location \
     --retry 5 --retry-delay 3 --retry-connrefused \
     ${HF_TOKEN:+-H "Authorization: Bearer $HF_TOKEN"} \
     "$MATERIALS_URL" -o /tmp/materials.zip
unzip -q -j -o /tmp/materials.zip 'golden/*' -d /tests/
rm -f /tmp/materials.zip

pip install --quiet --no-cache-dir \
    "numpy<3" "scipy<2" "soundfile==0.13.*" "pesq==0.0.4" "pystoi==0.4.*" \
    "librosa==0.11.*" "onnxruntime"
python3 /tests/judge.py \
        --enhanced /workspace/output/enhanced.wav \
        --clean /tests/clean.wav \
        --dnsmos-model /tests/sig_bak_ovr.onnx \
        --window-json /tests/window.json \
        --reward-json /logs/verifier/reward.json \
        --reward-txt /logs/verifier/reward.txt

