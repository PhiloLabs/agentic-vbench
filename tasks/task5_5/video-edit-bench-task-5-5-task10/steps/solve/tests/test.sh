#!/bin/bash
# Verifier: scores /workspace/output/solution.json against the inline
# CORRECT_ORDER baked into judge.py. Writes 0–1 reward to
# /logs/verifier/reward.json (and reward.txt for legacy readers).
set -euo pipefail

mkdir -p /logs/verifier /logs/artifacts

# Republish rollout outputs (solution.json + solution.mp4) into the
# bind-mounted /logs/artifacts so the host keeps them after sandbox teardown.
# Best-effort: an absent /workspace/output/ should not fail verification.
if [ -d /workspace/output ]; then
    cp -a /workspace/output/. /logs/artifacts/ 2>/dev/null || true
fi

python3 /tests/judge.py \
        --solution /workspace/output/solution.json \
        --reward-json /logs/verifier/reward.json \
        --reward-txt /logs/verifier/reward.txt
