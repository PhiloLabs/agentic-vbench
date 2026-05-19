#!/bin/bash
# Pre-agent fetch: pulls the per-task materials zip into /workspace/materials/.
# Runs in the container before the agent starts (Harbor multi-step setup hook).
set -euo pipefail

MATERIALS_URL="https://huggingface.co/datasets/ameddserM/video_edit_bench_task_5_5/resolve/main/materials/5.zip"

mkdir -p /workspace/materials /workspace/output /workspace/work

curl --fail --silent --show-error --location \
     --retry 5 --retry-delay 3 --retry-connrefused \
     ${HF_TOKEN:+-H "Authorization: Bearer $HF_TOKEN"} \
     "$MATERIALS_URL" -o /tmp/materials.zip
unzip -q -o /tmp/materials.zip -d /workspace/materials/
rm -f /tmp/materials.zip

mkdir -p /logs/artifacts
ls -la /workspace/materials/ > /logs/artifacts/materials-listing.txt

# Leave no trace of setup.sh in WORKDIR.
rm -- "$0"
