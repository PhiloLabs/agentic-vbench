#!/bin/bash
# Oracle: fetch the golden from HF at solve time, then copy to the
# agent-output path. MATERIALS_URL is injected via [solution.env] in
# task.toml — present only when Harbor runs the oracle agent.
set -euo pipefail

# Fetch the golden assets at solve time. MATERIALS_URL is injected via
# [solution.env] in task.toml — present only when Harbor runs the
# oracle agent. The agent step never sees this var.
mkdir -p /workspace/output /tmp/g
curl --fail --silent --show-error --location --retry 5 --retry-delay 3 \
     "$MATERIALS_URL" -o /tmp/g.zip
unzip -qo /tmp/g.zip 'golden/*' -d /tmp/g
mkdir -p /workspace/output
cp /tmp/g/golden/original.mp4 /workspace/output/output.mp4
echo "oracle: copied /tmp/g/golden/original.mp4 -> /workspace/output/output.mp4"
