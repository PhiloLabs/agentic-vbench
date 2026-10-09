#!/bin/bash
# Oracle solution: the census exactly as the rig's event log gives it.
#
# It ships the answer rather than deriving it from the pixels. The rig wrote
# the event log while it played, so this is the authoring-time record, not a
# solver, and it exists so the scorer can be shown to return 1.0 on the truth.
# What a real attempt scores is in calibration/scores.md.
set -euo pipefail

mkdir -p /workspace/output
cp "$(dirname "$0")/solution.json" /workspace/output/solution.json
echo "wrote /workspace/output/solution.json"
