#!/bin/bash
# Oracle: download the per-task materials zip and cp the bundled golden
# straight to the agent-output path. Ceiling-proof.
set -euo pipefail

MATERIALS_URL="https://huggingface.co/datasets/ameddserM/agentic_vbench_repair/resolve/main/materials/exp-codec-restore-task01.zip"

mkdir -p /workspace/output

curl --fail --silent --show-error --location \
     --retry 5 --retry-delay 3 --retry-connrefused \
     ${HF_TOKEN:+-H "Authorization: Bearer $HF_TOKEN"} \
     "$MATERIALS_URL" -o /tmp/materials.zip
unzip -q -j -o /tmp/materials.zip 'golden/clean.wav' -d /tmp/golden/
cp /tmp/golden/clean.wav /workspace/output/enhanced.wav
rm -rf /tmp/golden /tmp/materials.zip

echo "oracle: copied golden/clean.wav → /workspace/output/enhanced.wav"
