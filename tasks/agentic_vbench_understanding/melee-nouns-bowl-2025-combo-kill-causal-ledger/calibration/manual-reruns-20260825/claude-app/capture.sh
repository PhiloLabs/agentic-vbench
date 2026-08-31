#!/bin/bash
set -euo pipefail

: "${RUNNER:?set RUNNER to the harness name}"
: "${MODEL_NAME:?set MODEL_NAME to the exact model identifier}"
: "${HARNESS_VERSION:?set HARNESS_VERSION to the exact harness version}"

root=$(cd "$(dirname "$0")" && pwd)
run_dir="$root/run"
judge="$root/../../../steps/solve/tests/judge.py"

test -f "$run_dir/logs/network-policy.md" || {
    echo "missing $run_dir/logs/network-policy.md" >&2
    exit 1
}
test -f "$run_dir/output/solution.json" || {
    echo "missing $run_dir/output/solution.json" >&2
    exit 1
}

python3 "$judge" \
    --solution "$run_dir/output/solution.json" \
    --reward-json "$run_dir/logs/reward.json" \
    --reward-txt "$run_dir/logs/reward.txt"

RUN_DIR="$run_dir" RUNNER="$RUNNER" MODEL_NAME="$MODEL_NAME" \
HARNESS_VERSION="$HARNESS_VERSION" python3 - <<'PY'
import hashlib
import json
import os
from pathlib import Path

root = Path(os.environ["RUN_DIR"])
def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

manifest = {
    "condition": "full-baseline/manual",
    "runner": os.environ["RUNNER"],
    "model": os.environ["MODEL_NAME"],
    "harness_version": os.environ["HARNESS_VERSION"],
    "instruction_sha256": sha256(root / "instruction.md"),
    "media_sha256": sha256(root / "materials/match.mp4"),
    "solution_sha256": sha256(root / "output/solution.json"),
    "network_policy_evidence": "logs/network-policy.md",
}
(root / "logs/run-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
PY

echo "captured manual Claude app run in $run_dir/logs"
