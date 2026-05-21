#!/bin/bash
# Verifier: copies pre-baked golden references from /baked/golden/ into
# /tests/, then runs judge.py. Goldens never live in the agent's view of
# /workspace/.
set -euo pipefail

mkdir -p /logs/verifier /logs/artifacts /tests
if [ -d /workspace/output ]; then
    cp -a /workspace/output/. /logs/artifacts/ 2>/dev/null || true
fi
cp -r /baked/golden/. /tests/

python3 /tests/judge.py \
        --output-mp4 /workspace/output/output.mp4 \
        --clean-mp4 /tests/clean.mp4 \
        --corrupted-mp4 /workspace/materials/corrupted.mp4 \
        --mask-png /tests/mask.png \
        --task-type deblur \
        --gt-window-json /tests/gt_window.json \
        --reward-json /logs/verifier/reward.json \
        --reward-txt /logs/verifier/reward.txt
