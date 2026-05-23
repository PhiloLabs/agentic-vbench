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

# Fetch golden assets at verifier time. MATERIALS_URL is injected via
# [steps.verifier.env] in task.toml — not visible to the agent step.
mkdir -p /tests /tmp/g
curl --fail --silent --show-error --location --retry 5 --retry-delay 3 \
     "$MATERIALS_URL" -o /tmp/g.zip
unzip -qo /tmp/g.zip 'golden/*' -d /tmp/g
cp -r /tmp/g/golden/. /tests/
rm -rf /tmp/g.zip /tmp/g

python3 /tests/judge.py \
        --enhanced /workspace/output/enhanced.wav \
        --clean /tests/clean.wav \
        --dnsmos-model /tests/sig_bak_ovr.onnx \
        --window-json /tests/window.json \
        --reward-json /logs/verifier/reward.json \
        --reward-txt /logs/verifier/reward.txt

