#!/bin/bash
# Verifier: deterministic windowed color-restoration judge (LAB ΔE).
set -euo pipefail

mkdir -p /logs/verifier /logs/artifacts

if [ -d /workspace/output ]; then
    cp -a /workspace/output/. /logs/artifacts/ 2>/dev/null || true
fi

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
        --source-mp4 /workspace/materials/source.mp4 \
        --original-mp4 /tests/original.mp4 \
        --gt-window-json /tests/gt_window.json \
        --reward-json /logs/verifier/reward.json \
        --reward-txt /logs/verifier/reward.txt
