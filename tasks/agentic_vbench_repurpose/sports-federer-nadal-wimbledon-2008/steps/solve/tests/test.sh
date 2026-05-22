#!/bin/bash
# Verifier: VLM-judge the agent's repurpose.mp4 against the per-task rubric,
# then aggregate per-pillar JSONs into a single 0-1 reward at
# /logs/verifier/reward.json.
set -euo pipefail

mkdir -p /logs/verifier /logs/artifacts

# Diagnostic: confirm typing_extensions has Sentinel inside this container.
# Modal smokes failed with "Sentinel missing" even though the same check
# at build time and from a standalone Modal probe both pass — possibly
# the trial container differs from the build artifact.
{
  echo "=== typing_extensions trial-time diagnostic ==="
  which python3
  python3 -c "import typing_extensions, os; print('file:', typing_extensions.__file__); print('size:', os.path.getsize(typing_extensions.__file__)); print('has Sentinel:', hasattr(typing_extensions, 'Sentinel'))" 2>&1
  echo "=== all typing_extensions files anywhere ==="
  find / -name 'typing_extensions*' 2>/dev/null | head -20
  echo "=========================="
} | tee /logs/artifacts/te-diag.txt

# Stash agent output for forensics, even if the judge errors.
if [ -d /workspace/output ]; then
    cp -a /workspace/output/. /logs/artifacts/ 2>/dev/null || true
fi

# Build the workspace layout the judge expects.
WS=/tmp/repurpose_ws
RUN_ID=harbor_trial
rm -rf "$WS"
mkdir -p "$WS/runs/$RUN_ID/output" "$WS/results"
cp /baked/rubric.json   "$WS/rubric.json"
cp /baked/source.mp4    "$WS/source.mp4"
cp /baked/config.yaml   "$WS/config.yaml"
if [ ! -f /workspace/output/repurpose.mp4 ]; then
    mkdir -p /logs/verifier
    cat > /logs/verifier/reward.json <<'JSON'
{"reward": 0.0, "reason": "agent did not produce /workspace/output/repurpose.mp4"}
JSON
    echo "verifier: missing /workspace/output/repurpose.mp4 — wrote zero-reward and exiting"
    exit 0
fi
cp /workspace/output/repurpose.mp4 "$WS/runs/$RUN_ID/output/repurpose.mp4"

# Stub config.yaml under /tests/ — judge walks up from __file__ for it.
# Env vars (ANTHROPIC_API_KEY / GEMINI_API_KEY) override the empty values.
cp /baked/config.yaml /tests/config.yaml

# Run the judge. CUTBENCH_REPURPOSE_ONLY=1 skips golden-comparison (we have none).
export CUTBENCH_REPURPOSE_ONLY=1
python3 /tests/judge.py "$WS/runs/$RUN_ID" "$WS/source.mp4" "$RUN_ID" \
    2>&1 | tee /logs/artifacts/judge.log

# Aggregate per-pillar JSONs:
#   /logs/verifier/reward.json   — flat schema Harbor parses
#   /logs/artifacts/breakdown.json — rich per-pillar dump for debugging
python3 /tests/aggregate.py "$WS/results" "$RUN_ID" \
    /logs/verifier/reward.json \
    /logs/artifacts/breakdown.json
