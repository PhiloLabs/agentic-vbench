#!/bin/bash
# Pre-agent fetch: download the per-task materials zip and stage only the
# agent-facing inputs into /workspace/materials/. The verifier-only golden
# stays in the zip and is re-fetched by test.sh.
set -euo pipefail

MATERIALS_URL="https://huggingface.co/datasets/ameddserM/agentic_vbench_repair/resolve/main/materials/exp-codec-restore-task01.zip"

mkdir -p /workspace/materials /workspace/output /workspace/work

curl --fail --silent --show-error --location \
     --retry 5 --retry-delay 3 --retry-connrefused \
     ${HF_TOKEN:+-H "Authorization: Bearer $HF_TOKEN"} \
     "$MATERIALS_URL" -o /tmp/materials.zip

unzip -q -j -o /tmp/materials.zip 'input/*' -d /workspace/materials/
rm -f /tmp/materials.zip

mkdir -p /logs/artifacts
ls -la /workspace/materials/ > /logs/artifacts/materials-listing.txt

# Leave no trace of setup.sh in WORKDIR.
rm -- "$0"
