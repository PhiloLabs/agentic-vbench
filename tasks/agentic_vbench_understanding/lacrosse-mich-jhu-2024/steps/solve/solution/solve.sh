#!/bin/bash
# Oracle: the verified answer key (video-derived GT) is mounted verifier-side
# at /solution during the solution step only — never visible to the agent.
set -euo pipefail
mkdir -p /workspace/output
cp /solution/answer_key.json /workspace/output/solution.json
