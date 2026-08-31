#!/bin/bash
# Verifier entry point. Preserve the agent's output for the audit trail, then grade
# with the deterministic pure-stdlib scorer. No VLM/LLM judge.
set -euo pipefail

mkdir -p /logs/verifier /logs/artifacts

if [ -d /workspace/output ]; then
 cp -a /workspace/output/. /logs/artifacts/ 2>/dev/null || true
fi

python3 /tests/judge.py \
 --solution /workspace/output/solution.json \
 --reward-json /logs/verifier/reward.json \
 --reward-txt /logs/verifier/reward.txt
